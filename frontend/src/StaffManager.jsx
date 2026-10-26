import { useEffect, useRef, useState } from "react";

import { managementAuth } from "./managementAuth";

const BASE = "/api/v1/owner/staff/";

const EMPTY = {
  phone: "",
  first_name: "",
  last_name: "",
  is_active: true,
  permissions: [],
};

const PERMISSION_SECTIONS = {
  products: {
    title: "محصولات",
    models: {
      product: "محصولات",
      category: "دسته‌بندی‌ها",
      brand: "برندها",
      attribute: "ویژگی‌ها",
      attributevalue: "مقادیر ویژگی‌ها",
      categoryattribute: "ویژگی‌های دسته‌بندی",
      productattributevalue: "مشخصات محصولات",
      productvariant: "تنوع‌های محصول",
      productimage: "تصاویر محصولات",
    },
  },
  seo: {
    title: "سئو و نمایش در موتورهای جست‌وجو",
    models: {
      seosettings: "تنظیمات سئو",
      seosettingslog: "سوابق تغییرات سئو",
    },
  },
};

const PERMISSION_ACTIONS = {
  view: "مشاهده",
  add: "افزودن",
  change: "ویرایش",
  delete: "حذف",
};

function permissionGroups(catalog) {
  const groups = new Map();

  for (const permission of catalog) {
    const [app, codename = ""] = permission.key.split(".");
    const separator = codename.indexOf("_");
    const action = codename.slice(0, separator);
    const model = codename.slice(separator + 1);
    const section = PERMISSION_SECTIONS[app];

    const groupKey = `${app}.${model}`;

    if (!groups.has(groupKey)) {
      groups.set(groupKey, {
        key: groupKey,
        section: section?.title || "سایر دسترسی‌ها",
        title: section?.models[model] || "دسترسی تکمیلی",
        permissions: [],
      });
    }

    groups.get(groupKey).permissions.push({
      ...permission,
      label:
        PERMISSION_ACTIONS[action] ||
        "دسترسی ویژه",
      action,
    });
  }

  const actionOrder = ["view", "add", "change", "delete"];

  return [...groups.values()].map((group) => ({
    ...group,
    permissions: group.permissions.sort(
      (first, second) =>
        actionOrder.indexOf(first.action) -
        actionOrder.indexOf(second.action),
    ),
  }));
}

export default function StaffManager() {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [revision, setRevision] = useState(0);
  const [form, setForm] = useState(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const [notice, setNotice] = useState("");

  const lock = useRef(false);
  const editing = Boolean(form?.id);
    const groupedPermissions = permissionGroups(
    data?.permission_catalog || [],
  );

  function toggleGroup(permissions, checked) {
    const keys = permissions.map((permission) => permission.key);

    setForm((current) => ({
      ...current,
      permissions: checked
        ? [...new Set([...current.permissions, ...keys])]
        : current.permissions.filter((key) => !keys.includes(key)),
    }));
  }

  useEffect(() => {
    const controller = new AbortController();

    setData(null);
    setFailure("");

    const query = new URLSearchParams({
      page: String(page),
      search,
    });

    managementAuth.json(BASE + `?${query}`, {
      signal: controller.signal,
    })
      .then(setData)
      .catch((error) => {
        if (!controller.signal.aborted) {
          setFailure(error.message);
        }
      });

    return () => controller.abort();
  }, [page, search, revision]);

  function change(name, value) {
    setForm((current) => ({
      ...current,
      [name]: value,
    }));
  }

  function togglePermission(key, checked) {
    setForm((current) => ({
      ...current,
      permissions: checked
        ? [...new Set([...current.permissions, key])]
        : current.permissions.filter((item) => item !== key),
    }));
  }

  async function save(event) {
    event.preventDefault();

    if (lock.current) return;

    lock.current = true;
    setBusy(true);
    setFailure("");
    setNotice("");

    const payload = {
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
    };

    if (editing) {
      payload.is_active = form.is_active;

      if (!form.has_groups) {
        payload.permissions = form.permissions;
      }
    } else {
      payload.phone = form.phone.trim();
      payload.permissions = form.permissions;
    }

    try {
      await managementAuth.json(
        editing ? BASE + `${form.id}/` : BASE,
        {
          method: editing ? "PATCH" : "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        },
      );

      setForm(null);
      setNotice(
        editing
          ? "اطلاعات همکار ذخیره شد. ورود مجدد مدیریت او لازم است."
          : "همکار ساخته شد و با شماره و کد ورود وارد می‌شود.",
      );
      setRevision((value) => value + 1);
    } catch (error) {
      setFailure(error.message);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  function submitSearch(event) {
    event.preventDefault();

    const values = new FormData(event.currentTarget);

    setPage(1);
    setSearch(String(values.get("search") || "").trim());
    setForm(null);
    setRevision((value) => value + 1);
  }

  return (
    <section className="card">
      <div className="section-heading">
        <h2>مدیریت همکاران</h2>

        {data?.can_create && (
          <button
            type="button"
            className="button primary"
            disabled={busy}
            onClick={() => {
              setForm({ ...EMPTY, permissions: [] });
              setFailure("");
              setNotice("");
            }}
          >
            افزودن همکار
          </button>
        )}
      </div>

      {failure && (
        <div className="auth-error" role="alert">{failure}</div>
      )}

      {notice && (
        <div className="notice" role="status">{notice}</div>
      )}

      <form className="account-actions" onSubmit={submitSearch}>
        <input
          name="search"
          aria-label="جست‌وجوی همکار"
          placeholder="نام یا شماره موبایل"
          maxLength={150}
          disabled={busy}
        />
        <button
          type="submit"
          className="button ghost"
          disabled={busy}
        >
          جست‌وجو
        </button>
      </form>

      {!data && !failure && (
        <p role="status">در حال دریافت همکاران…</p>
      )}

      {form && data && (
        <form className="account-form account-spacing" onSubmit={save}>
          <h3>{editing ? "ویرایش همکار" : "همکار جدید"}</h3>

          <fieldset disabled={busy}>
            <div className="account-form-grid">
              <label className="account-field">
                <span>شماره موبایل</span>
                <input
                  value={form.phone}
                  onChange={(event) =>
                    change("phone", event.target.value)
                  }
                  readOnly={editing}
                  maxLength={32}
                  inputMode="tel"
                  dir="ltr"
                  required
                />
              </label>

              <label className="account-field">
                <span>نام</span>
                <input
                  value={form.first_name}
                  onChange={(event) =>
                    change("first_name", event.target.value)
                  }
                  maxLength={150}
                />
              </label>

              <label className="account-field">
                <span>نام خانوادگی</span>
                <input
                  value={form.last_name}
                  onChange={(event) =>
                    change("last_name", event.target.value)
                  }
                  maxLength={150}
                />
              </label>
            </div>

            {editing && (
              <label className="account-check">
                <input
                  type="checkbox"
                  checked={form.is_active}
                  onChange={(event) =>
                    change("is_active", event.target.checked)
                  }
                />
                حساب فعال باشد
              </label>
            )}

            {editing && (
              <p className="muted">
                غیرفعال‌کردن حساب، ورود مشتری و مدیریت این فرد
                را مسدود می‌کند.
              </p>
            )}

                        <div className="staff-access-heading">
              <h3>دسترسی‌های همکار</h3>
              <p>
                مشخص کن این همکار در هر بخش چه کارهایی می‌تواند
                انجام دهد. فقط دسترسی‌های موردنیازش را انتخاب کن.
              </p>
            </div>

            {form.has_groups ? (
              <div className="staff-access-note">
                دسترسی این همکار از طریق گروه کاربری هم تعیین
                می‌شود. تغییر آن به بررسی مدیر اصلی نیاز دارد.
              </div>
            ) : (
              <div className="staff-access-list">
                {groupedPermissions.map((group) => {
                  const selectedCount = group.permissions.filter(
                    (permission) =>
                      form.permissions.includes(permission.key),
                  ).length;

                  const allSelected =
                    selectedCount === group.permissions.length;

                  return (
                    <section
                      className="staff-access-card"
                      key={group.key}
                    >
                      <div className="staff-access-card-heading">
                        <div>
                          <span className="staff-access-section">
                            {group.section}
                          </span>
                          <h4>{group.title}</h4>
                        </div>

                        <label className="staff-access-all">
                          <input
                            type="checkbox"
                            checked={allSelected}
                            ref={(element) => {
                              if (element) {
                                element.indeterminate =
                                  selectedCount > 0 && !allSelected;
                              }
                            }}
                            onChange={(event) =>
                              toggleGroup(
                                group.permissions,
                                event.target.checked,
                              )
                            }
                          />
                          انتخاب همه
                        </label>
                      </div>

                      <div className="staff-access-options">
                        {group.permissions.map((permission) => {
                          const selected =
                            form.permissions.includes(
                              permission.key,
                            );

                          return (
                            <label
                              className={[
                                "staff-access-option",
                                selected ? "is-selected" : "",
                                permission.action === "delete"
                                  ? "is-delete"
                                  : "",
                              ].join(" ")}
                              key={permission.key}
                            >
                              <input
                                type="checkbox"
                                checked={selected}
                                onChange={(event) =>
                                  togglePermission(
                                    permission.key,
                                    event.target.checked,
                                  )
                                }
                              />
                              <span>{permission.label}</span>
                            </label>
                          );
                        })}
                      </div>
                    </section>
                  );
                })}

                {groupedPermissions.length === 0 && (
                  <div className="staff-access-note">
                    دسترسی قابل واگذاری ندارید.
                  </div>
                )}
              </div>
            )}
            <div className="account-actions">
              <button type="submit" className="button primary">
                {busy ? "در حال ذخیره…" : "ذخیره"}
              </button>
              <button
                type="button"
                className="button ghost"
                onClick={() => setForm(null)}
              >
                انصراف
              </button>
            </div>
          </fieldset>
        </form>
      )}

      {data && (
        <>
          <div className="table-scroll account-spacing">
            <table>
              <thead>
                <tr>
                  <th>نام</th>
                  <th>شماره</th>
                  <th>وضعیت</th>
                  <th>نوع حساب</th>
                  <th>عملیات</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((item) => (
                  <tr key={item.id}>
                    <td>{item.full_name || "ثبت نشده"}</td>
                    <td><bdi>{item.phone}</bdi></td>
                    <td>{item.is_active ? "فعال" : "غیرفعال"}</td>
                    <td>
                      {item.is_superuser ? "مدیر اصلی" : "همکار"}
                    </td>
                    <td>
                      {item.can_edit ? (
                        <button
                          type="button"
                          className="button ghost"
                          disabled={busy}
                          onClick={() => {
                            setForm({
                              ...item,
                              permissions: [...item.permissions],
                            });
                            setFailure("");
                            setNotice("");
                          }}
                        >
                          ویرایش
                        </button>
                      ) : (
                        <span className="muted">محافظت‌شده</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data.results.length === 0 && (
            <div className="empty">همکاری پیدا نشد.</div>
          )}

          <div className="account-actions">
            <button
              type="button"
              className="button ghost"
              disabled={busy || !data.previous}
              onClick={() => {
                setForm(null);
                setPage((value) => value - 1);
              }}
            >
              قبلی
            </button>

            <span>صفحهٔ {page.toLocaleString("fa-IR")}</span>

            <button
              type="button"
              className="button ghost"
              disabled={busy || !data.next}
              onClick={() => {
                setForm(null);
                setPage((value) => value + 1);
              }}
            >
              بعدی
            </button>
          </div>
        </>
      )}
    </section>
  );
}