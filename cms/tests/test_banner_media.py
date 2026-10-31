import struct
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from cms.api.v1.banner_views import BannerVideoUploadView
from cms.models import BannerVideo
from cms.services.banner_service import (
    banner_documents,
    get_banners,
    update_banners,
    validate_banners,
)
from cms.services.video_service import inspect_mp4, upload_video
from cms.tests.helpers import user
from cms.tests.test_banners import banner


def box(kind, body):
    return struct.pack('>I4s', len(body)+8, kind)+body


def fixture(codec=b'avc1', duration=2000):
    # Minimal metadata fixture; production additionally needs real encoded samples.
    avcc = box(b'avcC', b'\x01\x64\x00\x1f\xff\xe1\x00')
    sample = bytearray(78)
    struct.pack_into('>HH', sample, 24, 1280, 720)
    stsd = box(b'stsd', b'\x00'*4+struct.pack('>I', 1)+box(codec, bytes(sample)+avcc))
    hdlr = box(b'hdlr', b'\x00'*8+b'vide'+b'\x00'*12)
    trak = box(b'trak', box(b'mdia', hdlr+box(b'minf', box(b'stbl', stsd))))
    mvhd = b'\x00'*12+struct.pack('>II', 1000, duration)+b'\x00'*80
    return box(b'ftyp', b'isom\x00\x00\x00\x00isomavc1')+box(b'moov', box(b'mvhd', mvhd)+trak)+box(b'mdat', b'\x00'*32)


class BannerMediaTests(TestCase):
    def setUp(self):
        self.actor = user(is_staff=True, is_superuser=True)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.directory.name)
        self.override.enable()
        self.addCleanup(self.override.disable)

    def test_metadata_parses_and_rejects_wrong_codec_duration_and_truncation(self):
        self.assertEqual(inspect_mp4(fixture()), (1280, 720, 2.0))
        for data in [fixture(codec=b'hvc1'), fixture(duration=91000), fixture()[:-5], b'not mp4', fixture(duration=0)]:
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                inspect_mp4(data)

    def test_video_upload_persists_metadata_and_ignores_original_filename(self):
        video = upload_video(self.actor, SimpleUploadedFile('../../evil.html', fixture(), content_type='text/html'))
        self.assertTrue(video.file.name.endswith('.mp4'))
        self.assertNotIn('evil', video.file.name)
        self.assertEqual(video.duration, 2)
        self.assertEqual(video.width, 1280)

    def test_fake_video_and_oversize_rejected(self):
        with self.assertRaises(ValidationError):
            upload_video(self.actor, SimpleUploadedFile('fake.mp4', b'<script>alert(1)</script>'))
        upload = SimpleUploadedFile('big.mp4', b'x')
        upload.size = 31*1024*1024
        with self.assertRaises(ValidationError):
            upload_video(self.actor, upload)
        self.assertEqual(BannerVideo.objects.count(), 0)

    def test_video_reference_and_layout_validated(self):
        video = upload_video(self.actor, SimpleUploadedFile('demo.mp4', fixture()))
        row = banner(media_type='video', video_id=str(video.pk), alt='معرفی محصول', layout='overlay', interval=12)
        clean = validate_banners([row])[0]
        doc = banner_documents([clean])[0]
        self.assertEqual(doc['video_url'], video.file.url)
        self.assertEqual(doc['mobile_video_url'], video.file.url)
        for changed in [dict(row, video_id=None), dict(row, video_id='x'), dict(row, layout='javascript'), dict(row, interval=0), dict(row, overlay=True), dict(row, autoplay='yes'), dict(row, alt='')]:
            with self.subTest(changed=changed), self.assertRaises(ValidationError):
                validate_banners([changed])

    def test_old_banners_normalized_without_losing_content(self):
        old = banner(title='بنر قبلی')
        docs = banner_documents([old])
        self.assertEqual(docs[0]['title'], 'بنر قبلی')
        self.assertEqual(docs[0]['media_type'], 'image')
        self.assertEqual(docs[0]['layout'], 'split')
        record = update_banners(self.actor, get_banners().revision, [old])
        self.assertEqual(record.draft[0]['title'], old['title'])

    def test_customer_cannot_upload_even_if_superuser(self):
        request = APIRequestFactory().post('/', {'video': SimpleUploadedFile('a.mp4', fixture())}, format='multipart')
        force_authenticate(request, user=self.actor, token={'purpose': 'customer'})
        self.assertEqual(BannerVideoUploadView.as_view()(request).status_code, 403)
        self.assertFalse(BannerVideo.objects.exists())

    def test_manager_can_upload_and_response_has_no_private_path(self):
        request = APIRequestFactory().post('/', {'video': SimpleUploadedFile('a.mp4', fixture())}, format='multipart')
        force_authenticate(request, user=self.actor, token={'purpose': 'management'})
        response = BannerVideoUploadView.as_view()(request)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['url'].startswith('/media/'))
        self.assertNotIn(self.directory.name, str(response.data))
