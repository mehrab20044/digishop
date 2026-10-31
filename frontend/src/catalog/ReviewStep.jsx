import { pathLabel } from "./api";
export default function ReviewStep({ saved, choices, move, save }) {
  return (
    <>
      <div className="cw-review">
        <div>
          <span>محصول</span>
          <strong>{saved.name}</strong>
        </div>
        <div>
          <span>دسته‌بندی</span>
          <strong>{pathLabel(saved.category_id, choices.categories)}</strong>
        </div>
        <div>
          <span>تنوع‌ها</span>
          <strong>
            {saved.variants.length
              ? `${saved.variants.length} ترکیب ثبت‌شده`
              : "محصول ساده"}
          </strong>
        </div>
        <div>
          <span>تصاویر</span>
          <strong>{saved.images.length} تصویر</strong>
        </div>
      </div>
      {saved.issues.length ? (
        <div className="cw-checklist">
          <h4>این موارد را کامل کنید</h4>
          {saved.issues.map((issue, i) => (
            <button key={i} type="button" onClick={() => move(issue.step)}>
              {issue.message}
              <span>رفتن به مرحله ←</span>
            </button>
          ))}
        </div>
      ) : (
        <p className="cw-notice">
          اطلاعات لازم تکمیل است؛ می‌توانید محصول را منتشر کنید. موجودی صفر مانع
          انتشار نیست و محصول ناموجود نمایش داده می‌شود.
        </p>
      )}
      <div className="cw-actions">
        <button
          type="button"
          className="cw-primary"
          disabled={Boolean(saved.issues.length)}
          onClick={() => save(false, "published")}
        >
          انتشار در فروشگاه
        </button>
        <button type="button" onClick={() => save(false, "draft")}>
          نگه‌داشتن به‌عنوان پیش‌نویس
        </button>
        {saved.is_active && (
          <button type="button" onClick={() => save(false, "hidden")}>
            پنهان‌کردن از فروشگاه
          </button>
        )}
      </div>
    </>
  );
}
