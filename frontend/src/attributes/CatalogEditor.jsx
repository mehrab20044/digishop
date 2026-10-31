import DashboardSelect from "../components/DashboardSelect";
import { useEffect, useRef, useState } from "react";
import { managementFetch } from "../managementAuth";
import "./catalog-editor.css";
const BASE = "/api/v1/owner/catalog/";
async function request(path, body, method = "POST") {
  const response = await managementFetch(
    BASE + path,
    body === void 0
      ? {}
      : {
          method,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const messages = (value) =>
      typeof value === "string"
        ? [value]
        : value && typeof value === "object"
          ? Object.values(value).flatMap(messages)
          : [];
    throw new Error(
      messages(data?.error?.details || data?.error?.message || data).join(
        "\u060C ",
      ) ||
        "\u0630\u062E\u06CC\u0631\u0647 \u0627\u0646\u062C\u0627\u0645 \u0646\u0634\u062F.",
    );
  }
  return data;
}
function newAxis() {
  return {
    key: "option_" + crypto.randomUUID().slice(0, 8),
    label: "",
    values: [],
    required: true,
  };
}
function ValueInput({ rule, value, onChange }) {
  if (rule.value_type === "boolean" || rule.value_type === "choice")
    return (
      <DashboardSelect value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">انتخاب نشده</option>
        {(rule.value_type === "boolean"
          ? ["\u0628\u0644\u0647", "\u062E\u06CC\u0631"]
          : rule.choices
        ).map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </DashboardSelect>
    );
  return (
    <input
      value={value}
      inputMode={rule.value_type === "number" ? "decimal" : "text"}
      maxLength={255}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
function CatalogEditor({ productId, categoryId }) {
  const [data, setData] = useState(null),
    [definitions, setDefinitions] = useState([]),
    [values, setValues] = useState({}),
    [axes, setAxes] = useState([]),
    [rules, setRules] = useState([]),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [attempt, setAttempt] = useState(0),
    [tab, setTab] = useState("specs"),
    [draft, setDraft] = useState(null),
    [dirty, setDirty] = useState(false);
  const [definitionId, setDefinitionId] = useState("");
  const [definition, setDefinition] = useState({
    name: "",
    value_type: "text",
    unit: "",
    choices: [],
  });
  const lock = useRef(false);
  const live = useRef(false);
  const path = productId
    ? `products/${productId}/`
    : `categories/${categoryId}/`;
  function accept(result) {
    setData(result);
    setValues(result.values || {});
    setAxes(result.axes || []);
    setRules(result.own || []);
    setDirty(false);
  }
  useEffect(() => {
    live.current = true;
    let active = true;
    setData(null);
    Promise.all([
      request(path),
      productId ? Promise.resolve([]) : request("attributes/"),
    ])
      .then(([result, attrs]) => {
        if (active) {
          accept(result);
          setDefinitions(attrs);
        }
      })
      .catch((err) => {
        if (active) setError(err.message);
      });
    return () => {
      active = false;
      live.current = false;
    };
  }, [path, attempt]);
  useEffect(() => {
    if (!dirty) return;
    const warn = (e) => {
      e.preventDefault();
      e.returnValue = "";
    };
    const protect = (e) => {
      if (
        e.target.closest?.("a[href]") &&
        !window.confirm(
          "\u062A\u063A\u06CC\u06CC\u0631\u0627\u062A \u0645\u0634\u062E\u0635\u0627\u062A \u0630\u062E\u06CC\u0631\u0647 \u0646\u0634\u062F\u0647\u200C\u0627\u0646\u062F\u061B \u062E\u0627\u0631\u062C \u0645\u06CC\u200C\u0634\u0648\u06CC\u062F\u061F",
        )
      )
        e.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    document.addEventListener("click", protect);
    return () => {
      window.removeEventListener("beforeunload", warn);
      document.removeEventListener("click", protect);
    };
  }, [dirty]);
  async function run(action) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      if (live.current)
        setNotice("\u0630\u062E\u06CC\u0631\u0647 \u0634\u062F.");
    } catch (err) {
      if (live.current) setError(err.message);
    } finally {
      lock.current = false;
      if (live.current) setBusy(false);
    }
  }
  function save(action, body) {
    return run(async () => {
      const result = await request(path, {
        revision: data.revision,
        action,
        data: body,
      });
      if (live.current) {
        accept(result);
        setDraft(null);
      }
    });
  }
  function editAxis(index, key, value) {
    setDirty(true);
    setAxes((previous) =>
      previous.map((axis, i) =>
        i === index ? { ...axis, [key]: value } : axis,
      ),
    );
  }
  if (!data)
    return (
      <section className="card ce">
        <h3>مشخصات و تنوع‌ها</h3>
        {error ? (
          <>
            <p role="alert">{error}</p>
            <button onClick={() => setAttempt((v) => v + 1)}>
              دریافت دوباره
            </button>
          </>
        ) : (
          <p role="status">در حال دریافت…</p>
        )}
      </section>
    );
  return (
    <section className="card ce" dir="rtl">
      <header>
        <h3>
          {productId
            ? "\u0645\u0634\u062E\u0635\u0627\u062A \u0648 \u062A\u0646\u0648\u0639\u200C\u0647\u0627\u06CC \u0645\u062D\u0635\u0648\u0644"
            : "\u0648\u06CC\u0698\u06AF\u06CC\u200C\u0647\u0627\u06CC \u0627\u06CC\u0646 \u062F\u0633\u062A\u0647"}
        </h3>
        <span>
          {dirty
            ? "\u062A\u063A\u06CC\u06CC\u0631\u0627\u062A \u0630\u062E\u06CC\u0631\u0647 \u0646\u0634\u062F\u0647"
            : "\u0646\u0633\u062E\u0647\u0654 \u0630\u062E\u06CC\u0631\u0647\u200C\u0634\u062F\u0647"}
        </span>
      </header>
      {error && (
        <p className="ce-error" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="ce-notice" role="status">
          {notice}
        </p>
      )}
      <button
        disabled={busy}
        onClick={() => {
          if (
            dirty &&
            !window.confirm(
              "\u062A\u063A\u06CC\u06CC\u0631\u0627\u062A \u0630\u062E\u06CC\u0631\u0647\u200C\u0646\u0634\u062F\u0647 \u06A9\u0646\u0627\u0631 \u06AF\u0630\u0627\u0634\u062A\u0647 \u0634\u0648\u0646\u062F\u061F",
            )
          )
            return;
          setError("");
          setAttempt((v) => v + 1);
        }}
      >
        دریافت اطلاعات تازه
      </button>
      <fieldset disabled={busy}>
        {productId ? (
          <>
            <nav className="ce-actions" aria-label="بخش‌های مدیریت محصول">
              {[
                ["specs", "\u0645\u0634\u062E\u0635\u0627\u062A"],
                [
                  "axes",
                  "\u06AF\u0632\u06CC\u0646\u0647\u200C\u0647\u0627\u06CC \u0627\u0646\u062A\u062E\u0627\u0628\u06CC",
                ],
                [
                  "variants",
                  "\u0642\u06CC\u0645\u062A \u0648 \u0645\u0648\u062C\u0648\u062F\u06CC",
                ],
              ].map(([key, label]) => (
                <button
                  aria-pressed={tab === key}
                  key={key}
                  onClick={() => {
                    if (
                      dirty &&
                      !window.confirm(
                        "\u062A\u063A\u06CC\u06CC\u0631\u0627\u062A \u0627\u06CC\u0646 \u0628\u062E\u0634 \u0630\u062E\u06CC\u0631\u0647 \u0646\u0634\u062F\u0647\u200C\u0627\u0646\u062F. \u06A9\u0646\u0627\u0631 \u06AF\u0630\u0627\u0634\u062A\u0647 \u0634\u0648\u0646\u062F\u061F",
                      )
                    )
                      return;
                    accept(data);
                    setDraft(null);
                    setTab(key);
                  }}
                >
                  {label}
                </button>
              ))}
            </nav>
            <div hidden={tab !== "specs"}>
              <h4>۱. مشخصات محصول</h4>
              <p className="ce-help">
                ویژگی‌ها از دستهٔ اصلی و والدهای آن دریافت می‌شوند. مشخصات
                اجباری پیش از انتشار محصول باید کامل باشند.
              </p>
              <div className="ce-fields">
                {data.schema.map((rule) => (
                  <label key={rule.id}>
                    <span>
                      {rule.name}
                      {rule.required ? " *" : ""}
                      {rule.unit ? ` (${rule.unit})` : ""}
                    </span>
                    <ValueInput
                      rule={rule}
                      value={values[rule.id] || ""}
                      onChange={(value) => {
                        setDirty(true);
                        setValues({ ...values, [rule.id]: value });
                      }}
                    />
                  </label>
                ))}
              </div>
              {!data.schema.length && (
                <p>ابتدا در بخش دسته‌بندی، ویژگی‌های این دسته را تعیین کنید.</p>
              )}
              <button
                className="button primary"
                onClick={() =>
                  save(
                    "specs",
                    data.schema.map((rule) => ({
                      attribute_id: rule.id,
                      value: values[rule.id] || "",
                    })),
                  )
                }
              >
                ذخیرهٔ مشخصات
              </button>
            </div>
            <div hidden={tab !== "axes"}>
              <h4>۲. مشتری چه چیزهایی را انتخاب می‌کند؟</h4>
              <p className="ce-help">
                مثلاً رنگ، سایز، جنس یا وزن بسته. گزینه‌ها را با ویرگول جدا
                کنید. برای هر ترکیب، تنوع مستقل می‌سازید.
              </p>
              {axes.map((axis, index) => (
                <div className="ce-axis" key={axis.key}>
                  <label>
                    عنوان
                    <input
                      value={axis.label}
                      maxLength={80}
                      onChange={(e) => editAxis(index, "label", e.target.value)}
                    />
                  </label>
                  <label>
                    گزینه‌ها، مانند کوچک، متوسط، بزرگ
                    <input
                      value={axis.values.join("\u060C ")}
                      onChange={(e) =>
                        editAxis(
                          index,
                          "values",
                          e.target.value.split(/[,،]/).map((v) => v.trim()),
                        )
                      }
                    />
                  </label>
                  <label className="ce-check">
                    <input
                      type="checkbox"
                      checked={axis.required}
                      onChange={(e) =>
                        editAxis(index, "required", e.target.checked)
                      }
                    />
                    انتخاب الزامی
                  </label>
                  <button
                    onClick={() => {
                      setDirty(true);
                      setAxes(axes.filter((_, i) => i !== index));
                    }}
                  >
                    حذف ویژگی
                  </button>
                </div>
              ))}
              <div className="ce-actions">
                <button
                  disabled={busy || axes.length >= 6}
                  onClick={() => {
                    setDirty(true);
                    setAxes([...axes, newAxis()]);
                  }}
                >
                  + ویژگی انتخابی
                </button>
                <button
                  className="button primary"
                  onClick={() => save("axes", axes)}
                >
                  ذخیرهٔ گزینه‌ها
                </button>
              </div>
              <p className="ce-help">
                حذف یا تغییر گزینهٔ استفاده‌شده در تنوع رد می‌شود. برای
                اضافه‌کردن محور جدید به تنوع‌های قبلی، ابتدا الزامش را خاموش
                کنید، تنوع‌ها را تکمیل کنید و سپس الزام را روشن کنید.
              </p>
            </div>
            <div hidden={tab !== "variants"}>
              <h4>۳. قیمت و موجودی هر ترکیب</h4>
              <div className="ce-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>انتخاب</th>
                      <th>SKU</th>
                      <th>قیمت، تومان</th>
                      <th>موجودی</th>
                      <th>وضعیت</th>
                      <th>عملیات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.variants.map((v) => (
                      <tr key={v.id}>
                        <td>{v.label}</td>
                        <td dir="ltr">{v.sku}</td>
                        <td>
                          {new Intl.NumberFormat("fa-IR").format(v.price)}
                        </td>
                        <td>{v.stock}</td>
                        <td>
                          {v.is_active
                            ? "\u0641\u0639\u0627\u0644"
                            : "\u062E\u0627\u0645\u0648\u0634"}
                        </td>
                        <td>
                          <button
                            onClick={() => {
                              setDraft({ ...v, expected_stock: v.stock });
                              setDirty(true);
                            }}
                          >
                            ویرایش
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button
                disabled={!data.axes.length}
                onClick={() => {
                  setDraft({
                    sku: "",
                    options: {},
                    price: "",
                    stock: 0,
                    is_active: true,
                  });
                  setDirty(true);
                }}
              >
                + ساخت تنوع
              </button>
              {draft && (
                <div className="ce-variant">
                  <h4>
                    {draft.id
                      ? "\u0648\u06CC\u0631\u0627\u06CC\u0634 \u062A\u0646\u0648\u0639"
                      : "\u062A\u0646\u0648\u0639 \u062C\u062F\u06CC\u062F"}
                  </h4>
                  <div className="ce-fields">
                    {data.axes.map((axis) => (
                      <label key={axis.key}>
                        {axis.label}
                        {axis.required ? " *" : ""}
                        <DashboardSelect
                          value={draft.options[axis.key] || ""}
                          onChange={(e) => {
                            const options = { ...draft.options };
                            if (e.target.value)
                              options[axis.key] = e.target.value;
                            else delete options[axis.key];
                            setDraft({ ...draft, options });
                          }}
                        >
                          <option value="">انتخاب نشده</option>
                          {axis.values.map((v) => (
                            <option key={v} value={v}>
                              {v}
                            </option>
                          ))}
                        </DashboardSelect>
                      </label>
                    ))}
                    <label>
                      کد اختصاصی SKU
                      <input
                        dir="ltr"
                        value={draft.sku}
                        maxLength={100}
                        onChange={(e) =>
                          setDraft({ ...draft, sku: e.target.value })
                        }
                      />
                    </label>
                    <label>
                      قیمت، تومان
                      <input
                        type="number"
                        min="1"
                        step="1"
                        value={draft.price}
                        onChange={(e) =>
                          setDraft({ ...draft, price: e.target.value })
                        }
                      />
                    </label>
                    <label>
                      موجودی
                      <input
                        type="number"
                        min="0"
                        step="1"
                        value={draft.stock}
                        onChange={(e) =>
                          setDraft({ ...draft, stock: e.target.value })
                        }
                      />
                    </label>
                  </div>
                  <label className="ce-check">
                    <input
                      type="checkbox"
                      checked={draft.is_active}
                      onChange={(e) =>
                        setDraft({ ...draft, is_active: e.target.checked })
                      }
                    />
                    فعال و قابل انتخاب باشد
                  </label>
                  <div className="ce-actions">
                    <button
                      className="button primary"
                      onClick={() =>
                        save("variant", {
                          ...(draft.id
                            ? {
                                id: draft.id,
                                expected_stock: draft.expected_stock,
                              }
                            : {}),
                          sku: draft.sku,
                          options: draft.options,
                          price: Number(draft.price),
                          stock: Number(draft.stock),
                          is_active: draft.is_active,
                        })
                      }
                    >
                      ذخیرهٔ تنوع
                    </button>
                    <button
                      onClick={() => {
                        setDraft(null);
                        setDirty(false);
                      }}
                    >
                      بستن
                    </button>
                  </div>
                  <p className="ce-help">
                    موجودی، مقدار فعلی انبار است؛ هنگام رزرو و لغو سفارش به‌روز
                    می‌شود. برای توقف فروش تنوع آن را خاموش کنید؛ حذف تنوع انجام
                    نمی‌شود.
                  </p>
                </div>
              )}
            </div>
          </>
        ) : (
          <>
            <p className="ce-help">
              ویژگی‌های والد به این دسته ارث می‌رسند. موارد زیر برای خودِ این
              دسته هستند؛ تعریف محلی می‌تواند الزام والد را تغییر دهد.
            </p>
            <div className="ce-rules">
              {rules.map((rule, index) => (
                <div className="ce-axis" key={rule.attribute_id}>
                  <strong>
                    {definitions.find((a) => a.id === rule.attribute_id)?.name}
                  </strong>
                  <label className="ce-check">
                    <input
                      type="checkbox"
                      checked={rule.required}
                      onChange={(e) => {
                        setDirty(true);
                        setRules(
                          rules.map((r, i) =>
                            i === index
                              ? { ...r, required: e.target.checked }
                              : r,
                          ),
                        );
                      }}
                    />
                    اجباری
                  </label>
                  <button
                    onClick={() => {
                      setDirty(true);
                      setRules(rules.filter((_, i) => i !== index));
                    }}
                  >
                    برداشتن از دسته
                  </button>
                </div>
              ))}
            </div>
            <label>
              افزودن ویژگی موجود
              <DashboardSelect
                value=""
                onChange={(e) => {
                  if (!e.target.value) return;
                  setDirty(true);
                  setRules([
                    ...rules,
                    {
                      attribute_id: Number(e.target.value),
                      required: false,
                      sort_order: rules.length,
                    },
                  ]);
                }}
              >
                <option value="">ویژگی را انتخاب کنید</option>
                {definitions
                  .filter((a) => !rules.some((r) => r.attribute_id === a.id))
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
              </DashboardSelect>
            </label>
            <button
              className="button primary"
              onClick={() =>
                run(async () => {
                  const result = await request(
                    path,
                    { revision: data.revision, rules },
                    "PUT",
                  );
                  if (live.current) accept(result);
                })
              }
            >
              ذخیرهٔ ویژگی‌های دسته
            </button>
            <details>
              <summary>تعریف یا ویرایش ویژگی</summary>
              <label>
                ویژگی
                <DashboardSelect
                  value={definitionId}
                  onChange={(event) => {
                    const id = event.target.value;
                    setDefinitionId(id);
                    const found = definitions.find((a) => String(a.id) === id);
                    setDefinition(
                      found
                        ? {
                            name: found.name,
                            value_type: found.value_type,
                            unit: found.unit,
                            choices: found.choices,
                          }
                        : {
                            name: "",
                            value_type: "text",
                            unit: "",
                            choices: [],
                          },
                    );
                  }}
                >
                  <option value="">+ ویژگی جدید</option>
                  {definitions.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </DashboardSelect>
              </label>
              <div className="ce-fields">
                <label>
                  نام
                  <input
                    value={definition.name}
                    maxLength={100}
                    onChange={(e) =>
                      setDefinition({ ...definition, name: e.target.value })
                    }
                  />
                </label>
                <label>
                  نوع مقدار
                  <DashboardSelect
                    value={definition.value_type}
                    onChange={(e) =>
                      setDefinition({
                        ...definition,
                        value_type: e.target.value,
                        choices: [],
                      })
                    }
                  >
                    <option value="text">متن</option>
                    <option value="number">عدد</option>
                    <option value="boolean">بله / خیر</option>
                    <option value="choice">انتخاب از گزینه‌ها</option>
                  </DashboardSelect>
                </label>
                <label>
                  واحد، اختیاری
                  <input
                    value={definition.unit}
                    maxLength={30}
                    placeholder="مثلاً کیلوگرم"
                    onChange={(e) =>
                      setDefinition({ ...definition, unit: e.target.value })
                    }
                  />
                </label>
                {definition.value_type === "choice" && (
                  <label>
                    گزینه‌ها با ویرگول
                    <input
                      value={definition.choices.join("\u060C ")}
                      onChange={(e) =>
                        setDefinition({
                          ...definition,
                          choices: e.target.value
                            .split(/[,،]/)
                            .map((v) => v.trim()),
                        })
                      }
                    />
                  </label>
                )}
              </div>
              <button
                onClick={() =>
                  run(async () => {
                    const attribute = definitionId
                      ? await request(
                          `attributes/${definitionId}/`,
                          {
                            ...definition,
                            revision: definitions.find(
                              (a) => String(a.id) === definitionId,
                            ).revision,
                          },
                          "PUT",
                        )
                      : await request("attributes/", definition);
                    const freshCategory = await request(path);
                    if (live.current) {
                      setData(freshCategory);
                      setDefinitions((previous) => [
                        ...previous.filter((a) => a.id !== attribute.id),
                        attribute,
                      ]);
                      if (
                        !rules.some(
                          (rule) => rule.attribute_id === attribute.id,
                        )
                      )
                        setRules([
                          ...rules,
                          {
                            attribute_id: attribute.id,
                            required: false,
                            sort_order: rules.length,
                          },
                        ]);
                      setDirty(true);
                      setDefinitionId("");
                      setDefinition({
                        name: "",
                        value_type: "text",
                        unit: "",
                        choices: [],
                      });
                    }
                  })
                }
              >
                ذخیرهٔ تعریف ویژگی
              </button>
            </details>
            <h4>فرم نهایی محصول در این دسته</h4>
            <p>
              {data.effective
                .map(
                  (rule) =>
                    `${rule.name}${rule.required ? " (\u0627\u062C\u0628\u0627\u0631\u06CC)" : ""}`,
                )
                .join("\u060C ") ||
                "\u0647\u0646\u0648\u0632 \u0648\u06CC\u0698\u06AF\u06CC \u062A\u0639\u0631\u06CC\u0641 \u0646\u0634\u062F\u0647 \u0627\u0633\u062A."}
            </p>
          </>
        )}
      </fieldset>
    </section>
  );
}
export { CatalogEditor as default };
