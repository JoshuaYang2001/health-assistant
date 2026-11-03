import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// Import translation files
import commonEn from './locales/en/common.json';
import commonEl from './locales/el/common.json';
import commonZh from './locales/zh/common.json';

const syncDocumentLanguage = (language: string) => {
  document.documentElement.lang = language.startsWith('zh') ? 'zh-CN' : language;
};

i18n.on('languageChanged', syncDocumentLanguage);

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: commonEn },
      el: { translation: commonEl },
      zh: { translation: commonZh },
    },
    supportedLngs: ['en', 'el', 'zh'],
    load: 'languageOnly',
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false, // React already protects from XSS
    },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
    },
    react: {
      useSuspense: false, // Prevents white screen during loading
    },
  });

syncDocumentLanguage(i18n.resolvedLanguage || 'en');

export default i18n;
