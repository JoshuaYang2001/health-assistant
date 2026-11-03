import { pickLanguages } from '@neuronection/assistant-ui/languages';

export const UI_LANGUAGES = pickLanguages(['en', 'zh', 'el']).map(language =>
  language.code === 'zh' ? { ...language, nativeName: '简体中文' } : language,
);
