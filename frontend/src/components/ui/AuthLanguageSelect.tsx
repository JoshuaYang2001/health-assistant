import { useTranslation } from 'react-i18next';
import { UI_LANGUAGES } from '../../lib/uiLanguages';
import { useSettingsStore } from '../../store/slices/settingsSlice';

export function AuthLanguageSelect() {
  const { t, i18n } = useTranslation();

  return (
    <div className="flex items-center justify-end gap-2 mb-5 text-sm text-gray-600 dark:text-dark-muted">
      <label htmlFor="auth-language">{t('settings.language')}</label>
      <select
        id="auth-language"
        value={i18n.resolvedLanguage || 'en'}
        onChange={event => {
          const language = event.target.value;
          void i18n.changeLanguage(language);
          useSettingsStore.setState({ language });
        }}
        className="px-3 py-2 border border-gray-300 dark:border-dark-border rounded-lg bg-white dark:bg-dark-surface dark:text-dark-text"
      >
        {UI_LANGUAGES.map(language => (
          <option key={language.code} value={language.code}>{language.nativeName}</option>
        ))}
      </select>
    </div>
  );
}
