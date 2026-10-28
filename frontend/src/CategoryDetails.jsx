function CategoryLink({ id, children, navigate }) {
  const href = `/dashboard/categories/${id}`;

  return (
    <a
      href={href}
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "8px 14px",
        border: "1px solid #dce5f5",
        borderRadius: 9,
        background: "#fff",
        color: "#315bea",
        textDecoration: "none",
        fontSize: 13,
      }}
      onClick={(event) => {
        if (
          event.defaultPrevented ||
          event.button !== 0 ||
          event.ctrlKey ||
          event.metaKey ||
          event.shiftKey ||
          event.altKey
        ) {
          return;
        }

        event.preventDefault();
        navigate(href);
      }}
    >
      {children}
    </a>
  );
}

export default function CategoryDetails({ data, navigate }) {
  const related = data.related_categories || [];
  const attributes = data.allowed_attributes || [];

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <section
        style={{
          padding: 20,
          border: "1px solid #e4eaf3",
          borderRadius: 14,
          background: "#f8faff",
        }}
      >
        <h3 style={{ margin: "0 0 12px", fontSize: 14 }}>
          جایگاه این دسته
        </h3>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          {data.parent_id ? (
            <>
              <CategoryLink
                id={data.parent_id}
                navigate={navigate}
              >
                {data.parent || "دستهٔ بالاتر"}
              </CategoryLink>

              <span aria-hidden="true" style={{ color: "#94a3b8" }}>
                ←
              </span>

              <strong style={{ fontSize: 14 }}>
                {data.name}
              </strong>
            </>
          ) : (
            <>
              <strong style={{ fontSize: 14 }}>
                {data.name}
              </strong>
              <span
                style={{
                  padding: "4px 10px",
                  borderRadius: 7,
                  color: "#64748b",
                  background: "#edf1f7",
                  fontSize: 11,
                }}
              >
                دستهٔ مستقل
              </span>
            </>
          )}
        </div>

        <p
          style={{
            margin: "12px 0 0",
            fontSize: 12,
            color: "#748099",
          }}
        >
          {data.parent_id
            ? "این دسته زیرمجموعهٔ دستهٔ بالاتر است."
            : "این دسته در بالاترین سطح قرار دارد و والد ندارد."}
        </p>
      </section>

      <section>
        <h3 style={{ margin: "0 0 12px", fontSize: 14 }}>
          دسته‌های مرتبط
        </h3>

        {related.length ? (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 9 }}>
            {related.map((category) => (
              <CategoryLink
                key={category.id}
                id={category.id}
                navigate={navigate}
              >
                {category.name}
              </CategoryLink>
            ))}
          </div>
        ) : (
          <p className="muted">دستهٔ مرتبطی انتخاب نشده است.</p>
        )}
      </section>

      {data.description?.trim() && (
        <section>
          <h3 style={{ margin: "0 0 10px", fontSize: 14 }}>
            توضیحات
          </h3>
          <p
            style={{
              margin: 0,
              color: "#64748b",
              fontSize: 13,
              lineHeight: 2,
              whiteSpace: "pre-wrap",
              overflowWrap: "anywhere",
            }}
          >
            {data.description}
          </p>
        </section>
      )}

      {attributes.length > 0 && (
        <section>
          <h3 style={{ margin: "0 0 12px", fontSize: 14 }}>
            ویژگی‌های مجاز محصول
          </h3>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {attributes.map((attribute) => (
              <span
                key={attribute.id}
                style={{
                  padding: "6px 12px",
                  borderRadius: 8,
                  background: "#f1f4f9",
                  fontSize: 12,
                }}
              >
                {attribute.name}
              </span>
            ))}
          </div>
        </section>
      )}

      <details
        style={{
          borderTop: "1px solid #e7ebf2",
          paddingTop: 16,
        }}
      >
        <summary
          style={{
            cursor: "pointer",
            color: "#748099",
            fontSize: 12,
          }}
        >
          اطلاعات بیشتر
        </summary>

        <dl
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: 18,
            margin: "18px 0 0",
          }}
        >
          <div>
            <dt className="muted">نامک انگلیسی</dt>
            <dd style={{ margin: "6px 0 0", overflowWrap: "anywhere" }}>
              <bdi>{data.slug}</bdi>
            </dd>
          </div>
          <div>
            <dt className="muted">ترتیب نمایش</dt>
            <dd style={{ margin: "6px 0 0" }}>
              {Number(data.sort_order || 0).toLocaleString("fa-IR")}
            </dd>
          </div>
          <div>
            <dt className="muted">شناسه</dt>
            <dd style={{ margin: "6px 0 0" }}>
              {Number(data.id).toLocaleString("fa-IR")}
            </dd>
          </div>
        </dl>
      </details>
    </div>
  );
}