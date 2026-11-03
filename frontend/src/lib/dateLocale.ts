import { el, enUS, zhCN } from 'date-fns/locale';

export function getDateLocale(language: string) {
  const baseLanguage = language.toLowerCase().split('-')[0];
  if (baseLanguage === 'zh') return zhCN;
  if (baseLanguage === 'el') return el;
  return enUS;
}
