import './variant-picker.css';

const available = variant => variant.stock > 0 && variant.price > 0;

export default function VariantPicker({ axes = [], variants, selectedId, onChange }) {
  const selected = variants.find(variant => variant.id === selectedId);
  if (!axes.length) return <fieldset className="vp-axis"><legend>انتخاب مدل</legend><div className="vp-options">{variants.map(variant=><button type="button" key={variant.id} aria-pressed={variant.id===selectedId} onClick={()=>onChange(variant.id)}>{variant.label || [variant.color,variant.storage].filter(Boolean).join(' / ')}{!available(variant)&&<small>ناموجود</small>}</button>)}</div></fieldset>;
  function choose(key, value) {
    const candidates = variants.filter(variant => variant.options?.[key] === value);
    const score = variant => axes.filter(axis => axis.key !== key && variant.options?.[axis.key] === selected?.options?.[axis.key]).length;
    candidates.sort((a,b)=>score(b)-score(a)||Number(available(b))-Number(available(a))||a.price-b.price||a.id-b.id);
    if(candidates.length)onChange(candidates[0].id);
  }
  return <div className="vp-picker"><p>انتخاب ویژگی‌ها</p>{axes.map(axis=>{
    const choices = axis.values.filter(value=>variants.some(variant=>variant.options?.[axis.key]===value));
    if(!axis.required&&variants.some(variant=>!variant.options?.[axis.key]))choices.unshift(undefined);
    if(!choices.length)return null;
    return <fieldset className="vp-axis" key={axis.key}><legend>{axis.label}: <strong>{selected?.options?.[axis.key]||'انتخاب نشده'}</strong></legend><div className="vp-options">{choices.map(value=>{
      const inStock=variants.some(variant=>variant.options?.[axis.key]===value&&available(variant));
      return <button key={value??'__empty'} type="button" aria-pressed={selected?.options?.[axis.key]===value} onClick={()=>choose(axis.key,value)}>{value??'بدون انتخاب'}{!inStock&&<small>ناموجود</small>}</button>;
    })}</div></fieldset>;
  })}<small className="vp-note">گزینه‌ها به یک ترکیب واقعی متصل‌اند؛ تغییر یک ویژگی ممکن است انتخاب‌های دیگر را برای یافتن ترکیب موجود تغییر دهد.</small><p className="vp-selection" aria-live="polite">انتخاب فعلی: {selected?.label||'—'}</p></div>;
}
