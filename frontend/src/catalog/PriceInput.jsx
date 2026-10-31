import DashboardSelect from "../components/DashboardSelect";
import { useId, useState } from "react";
import { digits } from "./api";
const common = [100000, 200000, 300000, 500000, 750000, 1000000];
const clean = (v) => digits(v).replace(/[,\u066c\s]/g, "");
const label = (v) =>
  `${new Intl.NumberFormat("fa-IR").format(Number(v))} تومان`;
export default function PriceInput({
  value,
  onChange,
  presets = [],
  ariaLabel = "قیمت",
}) {
  const [custom, setCustom] = useState(false),
    [error, setError] = useState("");
  const id = useId();
  const amounts = [
    ...new Set(
      [...common, ...presets, value]
        .map((v) => Number(clean(v)))
        .filter((v) => Number.isSafeInteger(v) && v > 0),
    ),
  ].sort((a, b) => a - b);
  const canonical = clean(value);
  return (
    <div className="cw-price">
      <DashboardSelect
        aria-label={`انتخاب ${ariaLabel}`}
        value={custom ? "custom" : canonical || ""}
        onChange={(e) => {
          setError("");
          if (e.target.value === "custom") {
            setCustom(true);
          } else {
            setCustom(false);
            onChange(e.target.value);
          }
        }}
      >
        <option value="">انتخاب مبلغ…</option>
        {amounts.map((n) => (
          <option key={n} value={n}>
            {label(n)}
          </option>
        ))}
        <option value="custom">مبلغ دلخواه…</option>
      </DashboardSelect>
      {custom && (
        <input
          autoFocus
          aria-label={ariaLabel}
          aria-describedby={id}
          inputMode="numeric"
          autoComplete="off"
          placeholder="مثلاً 550,000"
          value={
            canonical ? canonical.replace(/\B(?=(\d{3})+(?!\d))/g, ",") : ""
          }
          onChange={(e) => {
            const next = clean(e.target.value);
            if (!/^\d*$/.test(next)) {
              setError("فقط رقم وارد کنید؛ مبلغ به تومان است.");
              return;
            }
            if (next.length > 16 || Number(next) > Number.MAX_SAFE_INTEGER) {
              setError("مبلغ از محدودهٔ مجاز بیشتر است.");
              return;
            }
            setError("");
            onChange(next);
          }}
        />
      )}
      <small
        id={id}
        className={error ? "cw-price-error" : ""}
        role={error ? "alert" : undefined}
      >
        {error ||
          (canonical
            ? label(canonical)
            : "مبلغ به تومان است؛ ورود دلخواه هم امکان دارد.")}
      </small>
    </div>
  );
}
