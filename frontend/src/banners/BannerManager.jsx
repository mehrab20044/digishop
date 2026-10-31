import DashboardSelect from "../components/DashboardSelect";
import { useEffect, useRef, useState } from "react";

import { pageRequest, writePage } from "../pages/page-api";
import { BannerCard } from "./Promotions";

import "../pages/page-builder.css";
import "./banners.css";

const PLACES = {
  hero: "اسلایدر اصلی",
  top: "تبلیغ بالای سایت",
  tiles: "تبلیغ‌های کنار هم",
  bottom: "تبلیغ پایین سایت",
};

function createBanner() {
  return {
    id: crypto.randomUUID(),
    placement: "hero",
    title: "بنر جدید",
    body: "",
    image_id: null,
    mobile_image_id: null,
    alt: "",
    href: "/products",
    button_label: "",
    enabled: true,
    show_text: false,
    start_at: null,
    end_at: null,
  };
}

function localTime(value) {
  if (!value) return "";

  const date = new Date(value);
  const offset = date.getTimezoneOffset() * 60000;

  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}

function serverTime(value) {
  return value ? new Date(value).toISOString() : null;
}

export default function BannerManager({ resource }) {
  const [record, setRecord] = useState(null);
  const [rows, setRows] = useState([]);
  const [baseline, setBaseline] = useState("");
  const [selected, setSelected] = useState(null);
  const [assets, setAssets] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [attempt, setAttempt] = useState(0);

  const lock = useRef(false);
  const mounted = useRef(false);

  const editable = Boolean(resource.capabilities?.change);
  const publishable = Boolean(resource.capabilities?.publish);
  const dirty = record !== null && JSON.stringify(rows) !== baseline;

  const current = rows.find((row) => row.id === selected);
  const currentIndex = rows.findIndex((row) => row.id === selected);

  useEffect(() => {
    mounted.current = true;

    return () => {
      mounted.current = false;
    };
  }, []);

  function accept(data) {
    setRecord(data);
    setRows(data.draft);
    setBaseline(JSON.stringify(data.draft));

    setSelected((previous) =>
      data.draft.some((row) => row.id === previous)
        ? previous
        : (data.draft[0]?.id ?? null),
    );

    setAssets((previous) => {
      const next = { ...previous };

      for (const row of data.preview) {
        for (const [idField, urlField] of [
          ["image_id", "image_url"],
          ["mobile_image_id", "mobile_image_url"],
          ["video_id", "video_url"],
          ["mobile_video_id", "mobile_video_url"],
        ]) {
          if (row[idField] && row[urlField]) {
            next[row[idField]] = row[urlField];
          }
        }
      }

      return next;
    });
  }

  useEffect(() => {
    const controller = new AbortController();

    setError("");

    pageRequest("banners/", { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) accept(data);
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(err.message);
      });

    return () => controller.abort();
  }, [attempt]);

  useEffect(() => {
    if (!dirty) return undefined;

    function beforeUnload(event) {
      event.preventDefault();
      event.returnValue = "";
    }

    function beforeNavigation(event) {
      const link = event.target.closest?.("a[href]");

      if (
        link &&
        !event.defaultPrevented &&
        !window.confirm("تغییرات ذخیره نشده‌اند. خارج می‌شوید؟")
      ) {
        event.preventDefault();
      }
    }

    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("click", beforeNavigation);

    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      document.removeEventListener("click", beforeNavigation);
    };
  }, [dirty]);

  async function perform(action) {
    if (lock.current) return;

    lock.current = true;
    setBusy(true);
    setError("");
    setNotice("");

    try {
      await action();
    } catch (err) {
      if (mounted.current) {
        setError(
          err.status === 409
            ? "نسخهٔ سرور تغییر کرده است. تغییرات شما حفظ شده‌اند؛ قبل از دریافت مجدد، آن‌ها را یادداشت کنید."
            : err.message,
        );
      }
    } finally {
      lock.current = false;
      if (mounted.current) setBusy(false);
    }
  }

  function patch(values) {
    setRows((previous) =>
      previous.map((row) =>
        row.id === selected ? { ...row, ...values } : row,
      ),
    );
  }

  function add() {
    const row = createBanner();

    setRows((previous) => [...previous, row]);
    setSelected(row.id);
  }

  function move(direction) {
    const destination = currentIndex + direction;

    if (destination < 0 || destination >= rows.length) return;

    const next = [...rows];
    const [item] = next.splice(currentIndex, 1);
    next.splice(destination, 0, item);

    setRows(next);
  }

  function remove() {
    if (!window.confirm("این بنر حذف شود؟")) return;

    const next = rows.filter((row) => row.id !== selected);

    setRows(next);
    setSelected(next[currentIndex]?.id ?? next.at(-1)?.id ?? null);
  }

  function upload(file, field) {
    const video = field.includes("video");
    const maximum = (video ? 30 : 5) * 1024 * 1024;

    if (file.size > maximum) {
      setError(
        video
          ? "ویدیو حداکثر ۳۰ مگابایت باشد."
          : "تصویر حداکثر ۵ مگابایت باشد.",
      );
      return;
    }

    const selectedId = selected;

    perform(async () => {
      const body = new FormData();
      body.set(video ? "video" : "image", file);

      const result = await pageRequest(video ? "banners/videos/" : "images/", {
        method: "POST",
        body,
      });

      if (!mounted.current) return;

      setAssets((previous) => ({
        ...previous,
        [result.id]: result.url,
      }));

      setRows((previous) =>
        previous.map((row) =>
          row.id === selectedId
            ? {
                ...row,
                [field]: result.id,
                alt: row.alt || row.title,
              }
            : row,
        ),
      );
    });
  }

  async function saveDraft() {
    if (!editable) throw new Error("مجوز ویرایش ندارید.");

    const data = await writePage(
      "banners/",
      { revision: record.revision, banners: rows },
      "PATCH",
    );

    if (mounted.current) accept(data);

    return data;
  }

  function save() {
    perform(async () => {
      await saveDraft();

      if (mounted.current) {
        setNotice("ذخیره شد؛ برای نمایش در سایت، انتشار را بزنید.");
      }
    });
  }

  function publish() {
    perform(async () => {
      const saved = dirty ? await saveDraft() : record;

      const data = await writePage("banners/", {
        revision: saved.revision,
      });

      if (mounted.current) {
        accept(data);
        setNotice("بنرها روی سایت منتشر شدند.");
      }
    });
  }

  if (!record) {
    return (
      <section className="card">
        <h2>بنرهای فروشگاه</h2>

        {error ? (
          <>
            <p role="alert">{error}</p>
            <button onClick={() => setAttempt((value) => value + 1)}>
              تلاش مجدد
            </button>
          </>
        ) : (
          <p role="status">در حال دریافت بنرها…</p>
        )}
      </section>
    );
  }

  const preview = current
    ? {
        ...current,
        image_url: assets[current.image_id] ?? null,
        mobile_image_url: assets[current.mobile_image_id] ?? null,
        video_url: assets[current.video_id] ?? null,
        mobile_video_url: assets[current.mobile_video_id] ?? null,
      }
    : null;

  const isVideo = current?.media_type === "video";

  return (
    <section className="pbe-manager" dir="rtl">
      <div className="pbe-intro">
        <div>
          <h2>بنرهای فروشگاه</h2>
          <p>تصویر را انتخاب کنید، لینک بدهید و منتشر کنید.</p>
        </div>

        <div className="pbe-editor-actions">
          {editable && (
            <button
              className="pbe-soft"
              disabled={busy || !dirty}
              onClick={save}
            >
              ذخیره
            </button>
          )}

          {publishable && (
            <button
              className="pbe-primary"
              disabled={busy || (dirty && !editable)}
              onClick={publish}
            >
              انتشار در سایت
            </button>
          )}
        </div>
      </div>

      {error && (
        <p className="pbe-error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="pbe-notice" role="status">
          {notice}
        </p>
      )}
      {busy && <p role="status">در حال انجام…</p>}

      <div className="ads-manager">
        <aside className="ads-list">
          <button
            className="pbe-primary"
            disabled={!editable || busy || rows.length >= 40}
            onClick={add}
          >
            + افزودن بنر
          </button>

          {rows.map((row) => (
            <button
              key={row.id}
              className={`ads-list-item ${
                selected === row.id ? "is-active" : ""
              }`}
              onClick={() => setSelected(row.id)}
              aria-pressed={selected === row.id}
            >
              {assets[row.image_id] ? (
                <img src={assets[row.image_id]} alt="" />
              ) : (
                <span aria-hidden="true">▧</span>
              )}

              <span>
                <strong>{row.title || "بنر جدید"}</strong>
                <small>
                  {PLACES[row.placement]} · {row.enabled ? "فعال" : "خاموش"}
                </small>
              </span>
            </button>
          ))}
        </aside>

        {current ? (
          <div className="ads-edit">
            <fieldset disabled={!editable || busy}>
              <label className="pbe-field">
                <span>نام بنر، فقط برای مدیریت</span>
                <input
                  value={current.title}
                  maxLength={160}
                  onChange={(event) => patch({ title: event.target.value })}
                />
              </label>

              <div className="pbe-two">
                <label className="pbe-field">
                  <span>کجا نمایش داده شود؟</span>
                  <DashboardSelect
                    value={current.placement}
                    onChange={(event) =>
                      patch({ placement: event.target.value })
                    }
                  >
                    {Object.entries(PLACES).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </DashboardSelect>
                </label>

                <label className="pbe-field">
                  <span>نوع فایل</span>
                  <DashboardSelect
                    value={isVideo ? "video" : "image"}
                    onChange={(event) =>
                      patch({ media_type: event.target.value })
                    }
                  >
                    <option value="image">تصویر</option>
                    <option value="video">ویدیو</option>
                  </DashboardSelect>
                </label>
              </div>

              <label className="ads-upload">
                <strong>{isVideo ? "انتخاب ویدیو" : "انتخاب تصویر بنر"}</strong>
                <span>
                  {isVideo
                    ? "MP4 / H.264، حداکثر ۳۰ مگابایت"
                    : "JPG، PNG یا WebP؛ حداکثر ۵ مگابایت"}
                </span>

                <input
                  type="file"
                  accept={
                    isVideo
                      ? "video/mp4,.mp4"
                      : "image/jpeg,image/png,image/webp"
                  }
                  onChange={(event) => {
                    const file = event.target.files?.[0];

                    if (file) {
                      upload(file, isVideo ? "video_id" : "image_id");
                    }

                    event.target.value = "";
                  }}
                />
              </label>

              <label className="pbe-field">
                <span>با کلیک روی بنر کجا برویم؟</span>
                <input
                  dir="ltr"
                  value={current.href}
                  placeholder="/products"
                  maxLength={1000}
                  onChange={(event) => patch({ href: event.target.value })}
                />
                <small>مثلاً /products یا آدرس کامل یک صفحهٔ دسته‌بندی.</small>
              </label>

              <label className="bn-check">
                <input
                  type="checkbox"
                  checked={current.enabled}
                  onChange={(event) => patch({ enabled: event.target.checked })}
                />
                این بنر نمایش داده شود
              </label>

              <details className="ads-advanced">
                <summary>تنظیمات اختیاری</summary>

                <label className="pbe-field">
                  <span>توضیح تصویر برای دسترس‌پذیری</span>
                  <input
                    value={current.alt}
                    maxLength={250}
                    onChange={(event) => patch({ alt: event.target.value })}
                  />
                </label>

                <label className="pbe-field">
                  <span>تصویر مخصوص موبایل</span>
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) upload(file, "mobile_image_id");
                      event.target.value = "";
                    }}
                  />
                </label>

                {current.mobile_image_id && (
                  <button
                    type="button"
                    className="pbe-link"
                    onClick={() => patch({ mobile_image_id: null })}
                  >
                    حذف تصویر موبایل
                  </button>
                )}

                {isVideo && (
                  <>
                    <label className="pbe-field">
                      <span>تصویر پیش از پخش ویدیو، اختیاری</span>
                      <input
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        onChange={(event) => {
                          const file = event.target.files?.[0];
                          if (file) upload(file, "image_id");
                          event.target.value = "";
                        }}
                      />
                    </label>

                    <label className="bn-check">
                      <input
                        type="checkbox"
                        checked={Boolean(current.autoplay)}
                        onChange={(event) =>
                          patch({ autoplay: event.target.checked })
                        }
                      />
                      پخش خودکار بی‌صدا
                    </label>
                  </>
                )}

                <div className="pbe-two">
                  <label className="pbe-field">
                    <span>شروع نمایش</span>
                    <input
                      type="datetime-local"
                      value={localTime(current.start_at)}
                      onChange={(event) =>
                        patch({ start_at: serverTime(event.target.value) })
                      }
                    />
                  </label>

                  <label className="pbe-field">
                    <span>پایان نمایش</span>
                    <input
                      type="datetime-local"
                      value={localTime(current.end_at)}
                      onChange={(event) =>
                        patch({ end_at: serverTime(event.target.value) })
                      }
                    />
                  </label>
                </div>
              </details>
            </fieldset>

            <div className="ads-actions">
              <button
                disabled={!editable || busy || currentIndex === 0}
                onClick={() => move(-1)}
              >
                ↑ زودتر نمایش بده
              </button>

              <button
                disabled={!editable || busy || currentIndex === rows.length - 1}
                onClick={() => move(1)}
              >
                ↓ دیرتر نمایش بده
              </button>

              <button
                className="ads-delete"
                disabled={!editable || busy}
                onClick={remove}
              >
                حذف بنر
              </button>
            </div>

            <div
              className="ads-preview"
              onClickCapture={(event) => {
                if (event.target.closest?.("a[href]")) {
                  event.preventDefault();
                }
              }}
            >
              <p>پیش‌نمایش — کل بنر در سایت قابل کلیک است.</p>
              <BannerCard banner={preview} />
            </div>
          </div>
        ) : (
          <div className="ads-empty">برای شروع، «افزودن بنر» را بزن.</div>
        )}
      </div>
    </section>
  );
}
