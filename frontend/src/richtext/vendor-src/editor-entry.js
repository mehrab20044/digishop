import { Editor } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import { TextStyleKit } from '@tiptap/extension-text-style';
import TextAlign from '@tiptap/extension-text-align';
export function createEditor(options) {
  return new Editor({
    ...options,
    extensions: [StarterKit.configure({heading:{levels:[2,3,4]},code:false,codeBlock:false,link:{openOnClick:false,autolink:false,protocols:['http','https']}}), TextStyleKit.configure({backgroundColor:false,lineHeight:false}),TextAlign.configure({types:['heading','paragraph'],defaultAlignment:'right'})],
    editorProps:{attributes:{class:'rt-editable',dir:'rtl',role:'textbox','aria-multiline':'true','aria-label':options.label||'توضیحات محصول'}},
  });
}
