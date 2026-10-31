import DashboardSelect from "../components/DashboardSelect";
import { useState } from "react";
import { ValueField } from "./shared";
import { splitValues } from "./api";
const types = {
  text: "متن آزاد",
  number: "عدد با واحد",
  boolean: "بله / خیر",
  choice: "انتخاب از فهرست",
};
export default function SpecificationsStep({
  saved,
  specs,
  setSpecs,
  setDirty,
  choices,
  applySpecification,
  onPending,
}) {
  const [open, setOpen] = useState(false),
    [mode, setMode] = useState("existing"),
    [selected, setSelected] = useState(""),
    [name, setName] = useState(""),
    [type, setType] = useState("text"),
    [unit, setUnit] = useState(""),
    [options, setOptions] = useState(""),
    [value, setValue] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const used = new Set(saved.schema.map((r) => r.id));
  const available = choices.attributes.filter((a) => !used.has(a.id));
  const current =
    mode === "existing"
      ? available.find((a) => a.id === Number(selected))
      : {
          name: name || "مقدار ویژگی",
          value_type: type,
          unit,
          choices: splitValues(options),
        };
  const canAttach =
    choices.permissions.change_category &&
    choices.permissions.add_categoryattribute;
  const canEdit =
    choices.permissions.add_productattributevalue &&
    choices.permissions.change_productattributevalue &&
    choices.permissions.delete_productattributevalue;
  function close() {
    setOpen(false);
    onPending(false);
    setError("");
  }
  return (
    <>
      <div className="cw-inherited">
        <strong>مشخصات یعنی توضیحات ثابت محصول</strong>
        <p>
          مثلاً «جنس پارچه: پنبه» یا «نوع آستین: بلند». گزینه‌هایی که مشتری برای
          خرید انتخاب می‌کند، مانند سایز و رنگ، در مرحلهٔ بعد ساخته می‌شوند.
        </p>
      </div>
      {saved.schema.length ? (
        <div className="cw-form-grid">
          {saved.schema.map((rule) => (
            <ValueField
              key={rule.id}
              rule={rule}
              value={specs[rule.id] || ""}
              onChange={(v) => {
                setSpecs((s) => ({ ...s, [rule.id]: v }));
                setDirty(true);
              }}
            />
          ))}
        </div>
      ) : (
        <div className="cw-empty">
          <h4>اولین مشخصهٔ این محصول را همین‌جا اضافه کنید</h4>
          <p>
            نیازی به خروج از فرم محصول نیست؛ ویژگی را بسازید، مقدار بدهید و
            اعمال کنید.
          </p>
        </div>
      )}
      {!open ? (
        <div className="cw-inline-start">
          <button
            type="button"
            className="cw-primary"
            disabled={!canAttach || !canEdit}
            onClick={() => {
              setOpen(true);
              onPending(true);
              setMode(available.length ? "existing" : "new");
              setValue("");
              setError("");
            }}
          >
            + افزودن مشخصه به محصول
          </button>
          <small>
            {canAttach
              ? "ویژگی جدید به‌صورت اختیاری به دستهٔ اصلی این محصول اضافه می‌شود؛ دیگر محصولات آن دسته هم می‌توانند از آن استفاده کنند."
              : "برای افزودن مشخصه، مجوز ویرایش دسته و افزودن ویژگی دسته لازم است."}
          </small>
        </div>
      ) : (
        <div className="cw-inline-spec">
          <div className="cw-section-heading">
            <div>
              <h4>افزودن مشخصه، بدون خروج از محصول</h4>
              <p>ویژگی آماده را استفاده کنید یا یک ویژگی جدید بسازید.</p>
            </div>
            <button type="button" disabled={busy} onClick={close}>
              بستن
            </button>
          </div>
          <div className="cw-mode">
            <button
              type="button"
              aria-pressed={mode === "existing"}
              onClick={() => {
                setMode("existing");
                setValue("");
              }}
            >
              استفاده از ویژگی موجود<span>مثلاً جنس، وزن، کشور سازنده</span>
            </button>
            <button
              type="button"
              aria-pressed={mode === "new"}
              disabled={!choices.permissions.add_attribute}
              onClick={() => {
                setMode("new");
                setValue("");
              }}
            >
              ساخت ویژگی جدید<span>نام، نوع پاسخ و مقدار همین محصول</span>
            </button>
          </div>
          {mode === "existing" ? (
            <label>
              نام ویژگی
              <DashboardSelect
                aria-label="انتخاب ویژگی موجود"
                value={selected}
                onChange={(e) => {
                  setSelected(e.target.value);
                  setValue("");
                }}
              >
                <option value="">ویژگی را انتخاب کنید</option>
                {available.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </DashboardSelect>
              {!available.length && (
                <small>
                  تمام ویژگی‌های موجود اینجا استفاده شده‌اند؛ ویژگی جدید بسازید.
                </small>
              )}
            </label>
          ) : (
            <div className="cw-form-grid">
              <label>
                نام ویژگی
                <input
                  maxLength={100}
                  placeholder="مثلاً جنس پارچه"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </label>
              <label>
                نوع پاسخ
                <DashboardSelect
                  value={type}
                  onChange={(e) => {
                    setType(e.target.value);
                    setValue("");
                  }}
                >
                  {Object.entries(types).map(([k, label]) => (
                    <option key={k} value={k}>
                      {label}
                    </option>
                  ))}
                </DashboardSelect>
              </label>
              {type === "number" && (
                <label>
                  واحد، اختیاری
                  <input
                    maxLength={30}
                    value={unit}
                    placeholder="مثلاً گرم"
                    onChange={(e) => setUnit(e.target.value)}
                  />
                </label>
              )}
              {type === "choice" && (
                <label>
                  پاسخ‌های مجاز
                  <textarea
                    placeholder="پنبه، کتان، پلی‌استر"
                    value={options}
                    onChange={(e) => setOptions(e.target.value)}
                  />
                  <small>با ویرگول یا خط جدید جدا کنید.</small>
                </label>
              )}
            </div>
          )}
          {current && (
            <div className="cw-inset">
              <strong>مقدار برای همین محصول</strong>
              <ValueField rule={current} value={value} onChange={setValue} />
              <small>
                مثال: نام ویژگی «جنس پارچه»، مقدار این محصول «پنبه».
              </small>
            </div>
          )}
          {error && (
            <p role="alert" className="cw-error">
              {error}
            </p>
          )}
          <div className="cw-actions">
            <button
              type="button"
              className="cw-primary"
              disabled={
                busy ||
                !current ||
                (mode === "new" && !name.trim()) ||
                !value.trim()
              }
              onClick={async () => {
                setBusy(true);
                setError("");
                try {
                  const ok = await applySpecification(
                    mode === "new"
                      ? {
                          definition: {
                            name: name.trim(),
                            value_type: type,
                            unit: type === "number" ? unit.trim() : "",
                            choices:
                              type === "choice" ? splitValues(options) : [],
                          },
                          value,
                        }
                      : { attribute_id: Number(selected), value },
                  );
                  if (ok) {
                    close();
                    setName("");
                    setOptions("");
                    setValue("");
                  }
                } catch (err) {
                  setError(err.message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              {busy
                ? "در حال ذخیره…"
                : mode === "new"
                  ? "ساخت ویژگی و اعمال به محصول"
                  : "افزودن و اعمال به محصول"}
            </button>
            <button type="button" disabled={busy} onClick={close}>
              انصراف
            </button>
          </div>
          <small>
            اعمال این مشخصه، مقادیر دیگری را هم که در همین مرحله ویرایش کرده‌اید
            یک‌جا ذخیره می‌کند.
          </small>
        </div>
      )}
    </>
  );
}
