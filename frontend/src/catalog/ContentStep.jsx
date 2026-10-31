import ProductGallery from "../ProductGallery";
import RichTextEditor from "../richtext/RichTextEditor";
export default function ContentStep({ saved, basic, change }) {
  return (
    <>
      <ProductGallery productId={saved.id} />
      <label>
        معرفی کوتاه
        <textarea
          maxLength={500}
          rows={3}
          value={basic.short_description}
          onChange={(e) => change("short_description", e.target.value)}
        />
      </label>
      <RichTextEditor
        key={`long-${saved.version}`}
        name="long_description_html"
        html={basic.long_description_html}
        plainText={saved.long_description || saved.description || ""}
        label="توضیحات کامل"
      />
      <details>
        <summary>توضیحات تکمیلی گالری</summary>
        <RichTextEditor
          key={`gallery-${saved.version}`}
          name="gallery_description_html"
          html={basic.gallery_description_html}
          plainText={saved.gallery_description || ""}
          label="توضیحات گالری"
        />
      </details>
      <p className="cw-help">
        تصاویر هنگام آپلود ذخیره می‌شوند؛ متن با دکمهٔ «ذخیره و ادامه» ذخیره
        می‌شود.
      </p>
    </>
  );
}
