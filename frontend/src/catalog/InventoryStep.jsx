import DashboardSelect from "../components/DashboardSelect";
import PriceInput from "./PriceInput";
import { combinationKey as keyOf } from "./api";
export default function InventoryStep({
  vary,
  setVary,
  setDirty,
  saved,
  simple,
  setSimple,
  axes,
  setAxes,
  rows,
  setRows,
  busy,
  generate,
  bulk,
  setBulk,
  updateRow,
}) {
  return (
    <>
      <div className="cw-mode">
        <button
          type="button"
          aria-pressed={!vary}
          disabled={Boolean(saved.variants.length || saved.axes.length)}
          onClick={() => {
            setVary(false);
            setDirty(true);
          }}
        >
          محصول ساده<span>یک قیمت و یک موجودی</span>
        </button>
        <button
          type="button"
          aria-pressed={vary}
          onClick={() => {
            setVary(true);
            setDirty(true);
          }}
        >
          محصول دارای انتخاب
          <span>قیمت و موجودی هر سایز، رنگ یا ترکیب</span>
        </button>
      </div>
      {!vary ? (
        <div className="cw-form-grid">
          <label>
            قیمت، تومان
            <PriceInput
              value={simple.price}
              ariaLabel="قیمت محصول"
              onChange={(price) => {
                setSimple({ ...simple, price });
                setDirty(true);
              }}
            />
          </label>
          <label>
            موجودی
            <input
              inputMode="numeric"
              value={simple.stock}
              onChange={(e) => {
                setSimple({ ...simple, stock: e.target.value });
                setDirty(true);
              }}
            />
          </label>
        </div>
      ) : (
        <>
          <p className="cw-help">
            ابتدا گزینه‌ها را بنویسید؛ سپس ترکیب‌ها را بسازید. ترکیب‌های قبلی
            حفظ می‌شوند. موجودی صفر یعنی ناموجود.
          </p>
          {axes.map((axis, i) => (
            <div className="cw-axis" key={axis.key}>
              <label>
                انتخاب مشتری
                <input
                  maxLength={80}
                  placeholder="مثلاً سایز"
                  value={axis.label}
                  onChange={(e) => {
                    setAxes((a) =>
                      a.map((r, n) =>
                        n === i ? { ...r, label: e.target.value } : r,
                      ),
                    );
                    setDirty(true);
                  }}
                />
              </label>
              <label>
                مقدارها، با ویرگول جدا شوند
                <input
                  value={axis.values.join("، ")}
                  placeholder="M، L، XL"
                  onChange={(e) => {
                    setAxes((a) =>
                      a.map((r, n) =>
                        n === i
                          ? {
                              ...r,
                              values: e.target.value
                                .split(/[,،]/)
                                .map((v) => v.trim()),
                            }
                          : r,
                      ),
                    );
                    setDirty(true);
                  }}
                />
              </label>
              <button
                type="button"
                disabled={saved.axes.some((a) => a.key === axis.key)}
                onClick={() => {
                  setAxes((a) => a.filter((_, n) => n !== i));
                  setDirty(true);
                }}
              >
                حذف
              </button>
            </div>
          ))}
          <div className="cw-actions">
            <button
              type="button"
              disabled={axes.length >= 6}
              onClick={() => {
                setAxes((a) => [
                  ...a,
                  {
                    key: "option_" + crypto.randomUUID().slice(0, 8),
                    label: "",
                    values: [],
                    required: true,
                  },
                ]);
                setDirty(true);
              }}
            >
              + گزینهٔ انتخاب مشتری
            </button>
            <button type="button" disabled={!axes.length} onClick={generate}>
              ساخت / به‌روزرسانی جدول ترکیب‌ها
            </button>
          </div>
          {rows.length > 0 && (
            <>
              <div className="cw-bulk">
                <strong>تنظیم گروهی</strong>
                <DashboardSelect
                  aria-label="محور تنظیم گروهی"
                  value={bulk.axis}
                  onChange={(e) =>
                    setBulk({
                      ...bulk,
                      axis: e.target.value,
                      value: "",
                    })
                  }
                >
                  <option value="">تمام ردیف‌ها</option>
                  {axes.map((a) => (
                    <option key={a.key} value={a.key}>
                      {a.label}
                    </option>
                  ))}
                </DashboardSelect>
                {bulk.axis && (
                  <DashboardSelect
                    aria-label="مقدار تنظیم گروهی"
                    value={bulk.value}
                    onChange={(e) =>
                      setBulk({ ...bulk, value: e.target.value })
                    }
                  >
                    <option value="">انتخاب مقدار</option>
                    {axes
                      .find((a) => a.key === bulk.axis)
                      ?.values.map((v) => (
                        <option key={v}>{v}</option>
                      ))}
                  </DashboardSelect>
                )}
                <PriceInput
                  value={bulk.price}
                  presets={rows.map((r) => r.price)}
                  ariaLabel="قیمت گروهی"
                  onChange={(price) => setBulk({ ...bulk, price })}
                />
                <input
                  aria-label="موجودی گروهی"
                  placeholder="موجودی"
                  inputMode="numeric"
                  value={bulk.stock}
                  onChange={(e) => setBulk({ ...bulk, stock: e.target.value })}
                />
                <button
                  type="button"
                  disabled={Boolean(bulk.axis && !bulk.value)}
                  onClick={() => {
                    setRows((rs) =>
                      rs.map((r) =>
                        !bulk.axis || r.options[bulk.axis] === bulk.value
                          ? {
                              ...r,
                              ...(bulk.price !== ""
                                ? { price: bulk.price }
                                : {}),
                              ...(bulk.stock !== ""
                                ? { stock: bulk.stock }
                                : {}),
                            }
                          : r,
                      ),
                    );
                    setDirty(true);
                  }}
                >
                  اعمال به ردیف‌های انتخاب‌شده
                </button>
              </div>
              <div className="cw-table">
                <table>
                  <thead>
                    <tr>
                      <th>ترکیب</th>
                      <th>قیمت، تومان</th>
                      <th>موجودی</th>
                      <th>فعال</th>
                      <th>عملیات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, i) => (
                      <tr key={row.id || keyOf(row.options)}>
                        <td>
                          <strong>
                            {axes
                              .map((a) => row.options[a.key])
                              .filter(Boolean)
                              .join(" / ")}
                          </strong>
                          <small>
                            {row.sku || "کد کالا خودکار ساخته می‌شود"}
                          </small>
                        </td>
                        <td>
                          <PriceInput
                            value={row.price}
                            presets={rows.map((r) => r.price)}
                            ariaLabel={`قیمت ردیف ${i + 1}`}
                            onChange={(value) => updateRow(i, "price", value)}
                          />
                        </td>
                        <td>
                          <input
                            aria-label={`موجودی ردیف ${i + 1}`}
                            inputMode="numeric"
                            value={row.stock}
                            onChange={(e) =>
                              updateRow(i, "stock", e.target.value)
                            }
                          />
                        </td>
                        <td>
                          <input
                            aria-label={`فعال بودن ردیف ${i + 1}`}
                            type="checkbox"
                            checked={row.is_active}
                            onChange={(e) =>
                              updateRow(i, "is_active", e.target.checked)
                            }
                          />
                        </td>
                        <td>
                          {row.id ? (
                            <span className="cw-help">
                              برای توقف فروش، خاموش کنید.
                            </span>
                          ) : (
                            <button
                              type="button"
                              onClick={() => {
                                setRows((rs) => rs.filter((_, n) => n !== i));
                                setDirty(true);
                              }}
                            >
                              حذف از پیش‌نمایش
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </>
  );
}
