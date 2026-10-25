import { useEffect, useRef, useState } from "react";

const BASE = "/api/v1/owner/";

async function readResponse(response) {
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      data?.detail ??
        data?.error?.message ??
        (data ? JSON.stringify(data) : `خطای ${response.status}`),
    );
  }

  if (!data) {
    throw new Error("پاسخ سرور معتبر نیست.");
  }

  return data;
}

export default function ProductGallery({ productId }) {
  const [images, setImages] = useState([]);
  const [selected, setSelected] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const urls = useRef([]);
  const input = useRef(null);

  useEffect(() => {
    const controller = new AbortController();

    fetch(`${BASE}products/${productId}/gallery/`, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal: controller.signal,
    })
      .then(readResponse)
      .then((data) => {
        if (!controller.signal.aborted) {
          setImages(data.images);
        }
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          setError(err.message);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [productId]);

  useEffect(() => {
    return () => {
      urls.current.forEach((url) => URL.revokeObjectURL(url));
    };
  }, []);

  function clearSelection() {
    urls.current.forEach((url) => URL.revokeObjectURL(url));
    urls.current = [];
    setSelected([]);

    if (input.current) input.current.value = "";
  }

  function chooseFiles(event) {
    const files = Array.from(event.target.files ?? []);

    setError("");
    setNotice("");
    clearSelection();

    if (files.length > 10) {
      setError("در هر بار حداکثر ۱۰ تصویر انتخاب کن.");
      return;
    }

    if (files.some((file) => file.size > 5 * 1024 * 1024)) {
      setError("حجم هر تصویر باید حداکثر ۵ مگابایت باشد.");
      return;
    }

    const previews = files.map((file) => ({
      file,
      url: URL.createObjectURL(file),
    }));

    urls.current = previews.map((item) => item.url);
    setSelected(previews);
  }

  async function upload() {
    if (busy || selected.length === 0) return;

    setBusy(true);
    setError("");
    setNotice("");

    try {
      const csrf = await readResponse(
        await fetch(`${BASE}csrf/`, {
          credentials: "same-origin",
          headers: { Accept: "application/json" },
          cache: "no-store",
        }),
      );

      const body = new FormData();

      selected.forEach(({ file }) => {
        body.append("images", file);
      });

      const data = await readResponse(
        await fetch(`${BASE}products/${productId}/gallery/`, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            Accept: "application/json",
            "X-CSRFToken": csrf.csrfToken,
          },
          body,
        }),
      );

      setImages(data.images);
      clearSelection();
      setNotice("تصاویر در گالری محصول ذخیره شدند.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const gridStyle = {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))",
    gap: 14,
    margin: "20px 0",
  };

  const imageStyle = {
    display: "block",
    width: "100%",
    height: 140,
    objectFit: "contain",
    background: "#f5f8fc",
    borderRadius: 12,
  };

  return (
    <section
      style={{
        marginTop: 25,
        paddingTop: 25,
        borderTop: "1px solid #e3eaf4",
      }}
    >
      <div className="section-heading">
        <h2>گالری محصول</h2>
        <span className="counter">
          {images.length.toLocaleString("fa-IR")} تصویر
        </span>
      </div>

      {loading && <p role="status">در حال دریافت تصاویر…</p>}
      {error && <p role="alert" style={{ color: "#a33030" }}>{error}</p>}
      {notice && <div className="notice" role="status">{notice}</div>}

      <div style={gridStyle}>
        {images.map((image) => (
          <div key={image.id}>
            <a href={image.image} target="_blank" rel="noreferrer">
              <img
                src={image.image}
                alt={`تصویر محصول ${image.id}`}
                style={imageStyle}
                loading="lazy"
              />
            </a>

            <p className="muted">
              {image.is_primary ? "تصویر اصلی" : "تصویر گالری"}
            </p>
          </div>
        ))}
      </div>

      {!loading && images.length === 0 && (
        <p className="muted">هنوز تصویری ثبت نشده است.</p>
      )}

      <label
        className={`gallery-picker ${
          busy || loading ? "gallery-picker-disabled" : ""
        }`}
      >
        <input
          ref={input}
          className="gallery-picker-input"
          type="file"
          accept=".jpg,.jpeg,.png,.webp"
          multiple
          disabled={busy || loading}
          onChange={chooseFiles}
        />

        <span className="gallery-picker-icon" aria-hidden="true">
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
            <rect x="3" y="3" width="18" height="18" rx="4" />
            <circle cx="8.5" cy="8.5" r="1.5" />
            <path d="m21 15-5-5L5 21" />
            <path d="M12 4v4m-2-2h4" />
          </svg>
        </span>

        <strong>
          {busy
            ? "در حال آپلود تصاویر…"
            : loading
              ? "در حال دریافت گالری…"
              : selected.length
                ? `${selected.length.toLocaleString("fa-IR")} تصویر انتخاب شده`
                : "تصاویر محصول را انتخاب کن"}
        </strong>

        <span className="gallery-picker-description">
          برای انتخاب چند عکس، روی این کادر کلیک کن
        </span>

        <span className="gallery-picker-button" aria-hidden="true">
          {selected.length ? "تغییر انتخاب تصاویر" : "+ انتخاب تصاویر"}
        </span>

        <span className="gallery-picker-formats">
          JPG · PNG · WebP
          <span>حداکثر ۱۰ عکس، هر عکس تا ۵ مگابایت</span>
        </span>
      </label>

      {selected.length > 0 && (
        <>
          <div style={gridStyle}>
            {selected.map((item) => (
              <div key={item.url}>
                <img
                  src={item.url}
                  alt={`پیش‌نمایش ${item.file.name}`}
                  style={imageStyle}
                />
                <p
                  className="muted"
                  style={{ overflowWrap: "anywhere" }}
                >
                  {item.file.name}
                </p>
              </div>
            ))}
          </div>

          <div style={{ display: "flex", gap: 10 }}>
            <button
              className="button primary"
              disabled={busy}
              onClick={upload}
            >
              {busy ? "در حال آپلود…" : "آپلود و ذخیرهٔ تصاویر"}
            </button>

            <button
              className="button ghost"
              disabled={busy}
              onClick={clearSelection}
            >
              انصراف
            </button>
          </div>
        </>
      )}
    </section>
  );
}