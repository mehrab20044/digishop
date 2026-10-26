import { managementFetch } from "./managementAuth";
import { useEffect, useRef, useState } from "react";

const BASE = "/api/v1/owner/";

const fieldLabels = {
  name: "نام محصول",
  slug: "نامک",
  category: "دسته‌بندی",
  brand: "برند",
  price: "قیمت",
  stock: "موجودی",
  short_description: "توضیح کوتاه",
  long_description: "توضیحات کامل",
  gallery_description: "توضیحات گالری",
  images: "تصاویر",
  detail: "خطا",
  __all__: "اطلاعات محصول",
};

const productFields = [
  "name",
  "slug",
  "category",
  "brand",
  "price",
  "stock",
  "short_description",
  "long_description",
  "gallery_description",
];

async function readResponse(response) {
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const error = new Error(
      data?.error?.message ??
        data?.detail ??
        `درخواست انجام نشد؛ کد ${response.status}`,
    );

    error.status = response.status;
    error.details = data?.error?.details ?? data;
    throw error;
  }

  if (!data) {
    const error = new Error(
      "پاسخ سرور قابل‌خواندن نیست؛ نتیجهٔ ذخیره باید بررسی شود.",
    );
    error.uncertain = true;
    throw error;
  }

  return data;
}

async function loadAll(resource, signal) {
  const records = [];
  let page = 1;

  while (true) {
    const response = await managementFetch(
      `${BASE}${resource}/?page=${page}`,
      {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
        cache: "no-store",
        signal,
      },
    );

    const data = await readResponse(response);
    records.push(...data.results);

    if (!data.next) return records;

    page += 1;
  }
}

function errorText(value) {
  if (Array.isArray(value)) {
    return value.map(errorText).join("، ");
  }

  if (value && typeof value === "object") {
    return Object.entries(value)
      .map(([key, item]) => {
        const label = fieldLabels[key] ?? key;
        return `${label}: ${errorText(item)}`;
      })
      .join("؛ ");
  }

  return String(value ?? "");
}

export default function ProductCreate({ onClose, onSaved }) {
  const [choices, setChoices] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState("");
  const [selected, setSelected] = useState([]);
  const [createdProduct, setCreatedProduct] = useState(null);
  const [uncertain, setUncertain] = useState("");

  const createdRef = useRef(null);
  const submitting = useRef(false);
  const previewUrls = useRef([]);
  const fileInput = useRef(null);

  useEffect(() => {
    const controller = new AbortController();

    Promise.all([
      loadAll("categories", controller.signal),
      loadAll("brands", controller.signal),
    ])
      .then(([categories, brands]) => {
        if (!controller.signal.aborted) {
          setChoices({ categories, brands });
        }
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          setLoadError(err.message);
        }
      });

    return () => controller.abort();
  }, []);

  useEffect(() => {
    return () => {
      previewUrls.current.forEach((url) => {
        URL.revokeObjectURL(url);
      });
    };
  }, []);

  function clearImages() {
    previewUrls.current.forEach((url) => {
      URL.revokeObjectURL(url);
    });

    previewUrls.current = [];
    setSelected([]);

    if (fileInput.current) {
      fileInput.current.value = "";
    }
  }

  function chooseImages(event) {
    const files = Array.from(event.target.files ?? []);

    setError("");
    clearImages();

    if (files.length > 10) {
      setError("در هر بار حداکثر ۱۰ تصویر انتخاب کن.");
      return;
    }

    if (files.some((file) => file.size > 5 * 1024 * 1024)) {
      setError("حجم هر تصویر باید حداکثر ۵ مگابایت باشد.");
      return;
    }

    if (
      files.some(
        (file) => !/\.(jpe?g|png|webp)$/i.test(file.name),
      )
    ) {
      setError("فقط JPG، JPEG، PNG و WebP انتخاب کن.");
      return;
    }

    const previews = files.map((file) => ({
      file,
      url: URL.createObjectURL(file),
    }));

    previewUrls.current = previews.map((item) => item.url);
    setSelected(previews);
  }

  async function submit(event) {
    event.preventDefault();

    if (submitting.current || uncertain) return;

    // Read the form before disabling its fields.
    const values = new FormData(event.currentTarget);
    const payload = Object.fromEntries(
      productFields.map((name) => [
        name,
        values.get(name) ?? "",
      ]),
    );

    payload.brand = payload.brand || null;

    submitting.current = true;
    setBusy(true);
    setError("");

    let stage = "auth";
    let succeeded = false;

    try {
      setProgress("در حال بررسی اتصال…");

      const csrf = await readResponse(
        await managementFetch(`${BASE}csrf/`, {
          credentials: "same-origin",
          headers: { Accept: "application/json" },
          cache: "no-store",
        }),
      );

      let product = createdRef.current;

      if (!product) {
        stage = "create";
        setProgress("در حال ساخت محصول…");

        product = await readResponse(
          await managementFetch(`${BASE}products/create/`, {
            method: "POST",
            credentials: "same-origin",
            headers: {
              Accept: "application/json",
              "Content-Type": "application/json",
              "X-CSRFToken": csrf.csrfToken,
            },
            body: JSON.stringify(payload),
          }),
        );

        if (!Number.isInteger(product.id) || product.id < 1) {
          const err = new Error(
            "شناسهٔ محصول در پاسخ سرور موجود نیست.",
          );
          err.uncertain = true;
          throw err;
        }

        // Keep the ID before starting the upload.
        createdRef.current = product;
        setCreatedProduct(product);
      }

      if (selected.length > 0) {
        stage = "upload";
        setProgress("محصول ساخته شد؛ در حال آپلود تصاویر…");

        const body = new FormData();

        selected.forEach(({ file }) => {
          body.append("images", file);
        });

        await readResponse(
          await managementFetch(
            `${BASE}products/${product.id}/gallery/`,
            {
              method: "POST",
              credentials: "same-origin",
              headers: {
                Accept: "application/json",
                "X-CSRFToken": csrf.csrfToken,
              },
              body,
            },
          ),
        );
      }

      succeeded = true;
    } catch (err) {
      const ambiguous =
        !err.status ||
        err.status >= 500 ||
        err.uncertain;

      if (
        ambiguous &&
        (stage === "create" || stage === "upload")
      ) {
        setUncertain(stage);
      }

      const explanation = err.details
        ? errorText(err.details)
        : err.message;

      setError(
        createdRef.current
          ? `محصول با شناسهٔ ${createdRef.current.id} ساخته شده است. مرحلهٔ بعد کامل نشد: ${explanation}`
          : explanation,
      );
    } finally {
      submitting.current = false;
      setBusy(false);
      setProgress("");
    }

    if (succeeded) {
      onSaved();
    }
  }

  const imageStyle = {
    display: "block",
    width: "100%",
    height: 150,
    objectFit: "contain",
    background: "#f4f7fc",
    borderRadius: 12,
  };

  return (
    <section className="card editor">
      <div className="section-heading">
        <h2>افزودن محصول</h2>

        <button
          type="button"
          className="button ghost"
          disabled={busy}
          onClick={onClose}
        >
          بستن
        </button>
      </div>

      {!choices && !loadError && (
        <p role="status">
          در حال دریافت دسته‌بندی‌ها و برندها…
        </p>
      )}

      {loadError && (
        <p role="alert" style={{ color: "#a33030" }}>
          {loadError}
        </p>
      )}

      {error && (
        <div
          role="alert"
          style={{
            padding: 16,
            marginBottom: 20,
            background: "#fff0f0",
            color: "#9c3030",
            borderRadius: 12,
            overflowWrap: "anywhere",
          }}
        >
          {error}
        </div>
      )}

      {createdProduct && (
        <div className="notice" role="status">
          محصول شمارهٔ{" "}
          {createdProduct.id.toLocaleString("fa-IR")}
          {" "}ثبت شده؛ دوباره ساخته نمی‌شود.
        </div>
      )}

      {uncertain && (
        <div
          role="alert"
          style={{
            padding: 16,
            marginBottom: 20,
            background: "#fff8e8",
            borderRadius: 12,
          }}
        >
          <p>
            پاسخ قطعی سرور دریافت نشده است. برای جلوگیری
            از ثبت تکراری، ارسال دوباره متوقف شد.
          </p>

          <p className="muted">
            {uncertain === "create"
              ? "قبل از تلاش مجدد، وجود محصول را با نامک آن در Django Admin بررسی کن."
              : "قبل از تلاش مجدد، تصاویر همین محصول را در Django Admin بررسی کن."}
          </p>

          <a
            className="button ghost"
            href={
              createdProduct
                ? `http://localhost:8000/admin/products/product/${createdProduct.id}/change/`
                : "http://localhost:8000/admin/products/product/"
            }
            target="_blank"
            rel="noreferrer"
          >
            بررسی در Django Admin
          </a>
        </div>
      )}

      {choices && choices.categories.length === 0 && (
        <p role="alert">
          ابتدا از بخش دسته‌بندی‌ها یک دسته‌بندی بساز.
        </p>
      )}

      {choices && choices.categories.length > 0 && (
        <form onSubmit={submit}>
          <fieldset
            className="form-grid"
            disabled={
              busy ||
              Boolean(createdProduct) ||
              Boolean(uncertain)
            }
            style={{ border: 0, margin: 0, padding: 0 }}
          >
            <label className="field">
              <span>نام محصول</span>
              <input
                name="name"
                required
                maxLength={200}
              />
            </label>

            <label className="field">
              <span>نامک یکتا</span>
              <input
                name="slug"
                required
                maxLength={220}
                placeholder="مثلاً wireless-headphone-x2"
              />
            </label>

            <label className="field">
              <span>دسته‌بندی</span>
              <select
                name="category"
                defaultValue=""
                required
              >
                <option value="" disabled>
                  انتخاب دسته‌بندی
                </option>

                {choices.categories.map((category) => (
                  <option
                    key={category.id}
                    value={category.id}
                  >
                    {category.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>برند — اختیاری</span>
              <select name="brand" defaultValue="">
                <option value="">بدون برند</option>

                {choices.brands.map((brand) => (
                  <option key={brand.id} value={brand.id}>
                    {brand.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>قیمت پایه — مطابق واحد مبلغ Backend</span>
              <input
                name="price"
                type="number"
                min="0"
                step="1"
                required
              />
            </label>

            <label className="field">
              <span>موجودی پایه</span>
              <input
                name="stock"
                type="number"
                min="0"
                step="1"
                defaultValue="0"
                required
              />
            </label>

            <div className="full-width">
              <label className="field">
                <span>توضیح کوتاه</span>
                <input
                  name="short_description"
                  maxLength={500}
                />
              </label>
            </div>

            <label className="field">
              <span>توضیحات کامل</span>
              <textarea
                name="long_description"
                rows={4}
              />
            </label>

            <label className="field">
              <span>توضیحات گالری</span>
              <textarea
                name="gallery_description"
                rows={4}
              />
            </label>
          </fieldset>

          <div style={{ marginTop: 28 }}>
            <h3>تصاویر محصول</h3>

            <label
              className={`gallery-picker ${
                busy || uncertain
                  ? "gallery-picker-disabled"
                  : ""
              }`}
            >
              <input
                ref={fileInput}
                className="gallery-picker-input"
                type="file"
                accept=".jpg,.jpeg,.png,.webp"
                multiple
                disabled={busy || Boolean(uncertain)}
                onChange={chooseImages}
              />

              <span
                className="gallery-picker-icon"
                aria-hidden="true"
              >
                <svg
                  width="30"
                  height="30"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <rect
                    x="3"
                    y="3"
                    width="18"
                    height="18"
                    rx="4"
                  />
                  <circle cx="8.5" cy="8.5" r="1.5" />
                  <path d="m21 15-5-5L5 21" />
                </svg>
              </span>

              <strong>
                {selected.length
                  ? `${selected.length.toLocaleString("fa-IR")} تصویر انتخاب شده`
                  : "تصاویر محصول را انتخاب کن"}
              </strong>

              <span className="gallery-picker-description">
                برای انتخاب چند تصویر روی این کادر کلیک کن
              </span>

              <span
                className="gallery-picker-button"
                aria-hidden="true"
              >
                {selected.length
                  ? "تغییر انتخاب تصاویر"
                  : "+ انتخاب تصاویر"}
              </span>

              <span className="gallery-picker-formats">
                JPG · PNG · WebP
                <span>
                  حداکثر ۱۰ عکس، هر عکس تا ۵ مگابایت
                </span>
              </span>
            </label>

            {selected.length > 0 && (
              <>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns:
                      "repeat(auto-fill, minmax(130px, 1fr))",
                    gap: 14,
                    margin: "20px 0",
                  }}
                >
                  {selected.map((item, index) => (
                    <div key={item.url}>
                      <img
                        src={item.url}
                        alt={`پیش‌نمایش ${item.file.name}`}
                        style={imageStyle}
                      />

                      <p
                        className="muted"
                        style={{
                          marginTop: 7,
                          overflowWrap: "anywhere",
                        }}
                      >
                        {item.file.name}
                      </p>

                      {index === 0 && (
                        <small style={{ color: "#3768c7" }}>
                          تصویر اصلی در گالری خالی
                        </small>
                      )}
                    </div>
                  ))}
                </div>

                <button
                  type="button"
                  className="button ghost"
                  disabled={busy || Boolean(uncertain)}
                  onClick={clearImages}
                >
                  پاک‌کردن انتخاب تصاویر
                </button>
              </>
            )}
          </div>

          <p className="muted" style={{ margin: "22px 0" }}>
            محصول به‌صورت پیش‌نویس و غیرفعال ذخیره می‌شود.
            تصاویر انتخاب‌شده پس از ساخت، به همان محصول
            اضافه می‌شوند.
          </p>

          {busy && (
            <p role="status" aria-live="polite">
              {progress}
            </p>
          )}

          <div className="form-actions">
            <button
              className="button primary"
              type="submit"
              disabled={busy || Boolean(uncertain)}
            >
              {busy
                ? "در حال ذخیره…"
                : createdProduct
                  ? selected.length
                    ? "تلاش مجدد آپلود تصاویر"
                    : "پایان و بازگشت به فهرست"
                  : selected.length
                    ? "ساخت محصول و آپلود تصاویر"
                    : "ساخت محصول"}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}