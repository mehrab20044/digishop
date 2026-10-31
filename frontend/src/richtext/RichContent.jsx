import "./richtext.css";
// HTML is exclusively the server-sanitized HTML field, never a plain-text fallback.
export default function RichContent({html,plainText,className=''}){return html?<div className={`rt-content ${className}`} dangerouslySetInnerHTML={{__html:html}} />:<p className={`rt-plain ${className}`}>{plainText}</p>;}
