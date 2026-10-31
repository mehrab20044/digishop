import DashboardSelect from "../components/DashboardSelect";
import { CategorySelect, QuickCreate } from "./shared";
export default function BasicStep({ basic, choices, change, quick }) {
  return (
    <div className="cw-form-grid">
      <div>
        <label>
          نام محصول <span className="cw-required">الزامی</span>
          <input
            required
            maxLength={200}
            value={basic.name}
            placeholder="مثلاً پیراهن مردانه آکسفورد"
            onChange={(e) => change("name", e.target.value)}
          />
        </label>
        <label>
          دسته‌بندی <span className="cw-required">الزامی</span>
        </label>
        <CategorySelect
          rows={choices.categories}
          value={basic.category_id}
          onChange={(v) => change("category_id", v)}
        />
        {choices.permissions.add_category && (
          <QuickCreate
            kind="category"
            choices={choices}
            onSaved={(row) => quick("categories", row)}
          />
        )}
      </div>
      <div>
        <label>
          برند <small>اختیاری</small>
          <DashboardSelect
            value={basic.brand_id || ""}
            onChange={(e) =>
              change("brand_id", e.target.value ? Number(e.target.value) : null)
            }
          >
            <option value="">بدون برند</option>
            {choices.brands.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </DashboardSelect>
        </label>
        {choices.permissions.add_brand && (
          <QuickCreate
            kind="brand"
            choices={choices}
            onSaved={(row) => quick("brands", row)}
          />
        )}
        <details>
          <summary>تنظیم آدرس محصول، اختیاری</summary>
          <label>
            نامک
            <input
              value={basic.slug}
              maxLength={220}
              onChange={(e) => change("slug", e.target.value)}
            />
            <small>خالی باشد، سرور آدرس یکتا می‌سازد.</small>
          </label>
        </details>
      </div>
    </div>
  );
}
