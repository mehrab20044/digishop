from cms.models import PageImage


def public_document(page):
    # Published snapshot only; draft changes must never leak into public output.
    document = dict(page.published)
    blocks = [dict(block, data=dict(block["data"])) for block in document.get("blocks", []) if block.get("enabled")]
    ids = [block["data"].get("image_id") for block in blocks if block["data"].get("image_id")]
    images = {str(image.pk): image for image in PageImage.objects.filter(pk__in=ids)}
    for block in blocks:
        image = images.get(block["data"].get("image_id"))
        if image:
            block["data"]["image_url"] = image.file.url
            block["data"]["image_width"] = image.width
            block["data"]["image_height"] = image.height
    document["blocks"] = blocks
    return document
