import { beforeEach, describe, expect, it, vi } from 'vitest';
import { waitFor } from '@testing-library/react';
import i18n from '../../i18n';
import { useSettingsStore } from './settingsSlice';

const settingsApi = vi.hoisted(() => ({
  getDefinitions: vi.fn(),
  getEffective: vi.fn(),
  updateOverride: vi.fn(),
}));

vi.mock('../../services/settingsService', () => ({ settingsService: settingsApi }));

function persistedLanguage(): string | undefined {
  const stored = localStorage.getItem('settings-storage');
  return stored ? JSON.parse(stored).state.language : undefined;
}

describe('language preferences', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    localStorage.clear();
    await i18n.changeLanguage('en');
    useSettingsStore.setState(useSettingsStore.getInitialState(), true);
    useSettingsStore.setState({
      language: 'en',
      effectiveSettings: { 'localization.language': 'en' },
      settingsSources: { 'localization.language': 'user' },
    });
    settingsApi.getDefinitions.mockResolvedValue({ definitions: [], categories: [] });
    settingsApi.updateOverride.mockResolvedValue(undefined);
  });

  it('switches immediately and saves the Chinese preference for the next visit', async () => {
    await useSettingsStore.getState().updateUserSetting('localization.language', 'zh');

    expect(settingsApi.updateOverride).toHaveBeenCalledWith('user', 'localization.language', 'zh');
    expect(useSettingsStore.getState().language).toBe('zh');
    expect(useSettingsStore.getState().getSetting('localization.language')).toBe('zh');
    expect(i18n.resolvedLanguage).toBe('zh');
    expect(persistedLanguage()).toBe('zh');
    expect(localStorage.getItem('i18nextLng')).toBe('zh');
    expect(document.documentElement.lang).toBe('zh-CN');
  });

  it('rolls back the UI, both browser caches and the resolved preference if saving fails', async () => {
    settingsApi.updateOverride.mockRejectedValueOnce(new Error('Network error'));

    await expect(
      useSettingsStore.getState().updateUserSetting('localization.language', 'zh'),
    ).rejects.toThrow('Failed to save setting');

    expect(useSettingsStore.getState().language).toBe('en');
    expect(useSettingsStore.getState().getSetting('localization.language')).toBe('en');
    expect(i18n.resolvedLanguage).toBe('en');
    expect(persistedLanguage()).toBe('en');
    expect(localStorage.getItem('i18nextLng')).toBe('en');
    expect(document.documentElement.lang).toBe('en');
  });

  it('preserves the previous language through the header setter when the request fails', async () => {
    let rejectSave!: (reason: Error) => void;
    settingsApi.updateOverride.mockReturnValueOnce(new Promise<void>((_, reject) => {
      rejectSave = reject;
    }));

    useSettingsStore.getState().setLanguage('zh');
    expect(useSettingsStore.getState().language).toBe('zh');
    expect(i18n.resolvedLanguage).toBe('zh');

    rejectSave(new Error('Save rejected'));

    await waitFor(() => expect(useSettingsStore.getState().language).toBe('en'));
    expect(i18n.resolvedLanguage).toBe('en');
    expect(persistedLanguage()).toBe('en');
  });

  it('restores the previous language when there was no effective language entry yet', async () => {
    useSettingsStore.setState({ effectiveSettings: {} });
    settingsApi.updateOverride.mockRejectedValueOnce(new Error('Save rejected'));

    await expect(
      useSettingsStore.getState().updateUserSetting('localization.language', 'zh'),
    ).rejects.toThrow();

    expect(useSettingsStore.getState().language).toBe('en');
    expect(useSettingsStore.getState().effectiveSettings).toEqual({});
    expect(i18n.resolvedLanguage).toBe('en');
  });

  it('keeps the detected Chinese browser language when the server only supplies its default', async () => {
    await i18n.changeLanguage('zh-CN');
    useSettingsStore.setState({ language: 'zh' });
    settingsApi.getEffective.mockResolvedValueOnce({
      settings: { 'localization.language': 'en' },
      sources: { 'localization.language': 'default' },
    });

    await useSettingsStore.getState().loadSettings();

    expect(useSettingsStore.getState().language).toBe('zh');
    expect(useSettingsStore.getState().getSetting('localization.language')).toBe('zh');
    expect(i18n.resolvedLanguage).toBe('zh');
    expect(settingsApi.updateOverride).not.toHaveBeenCalled();
    expect(useSettingsStore.getState().settingsLoaded).toBe(true);
    expect(useSettingsStore.getState().settingsLoading).toBe(false);
    expect(useSettingsStore.getState().getSettingSource('localization.language')).toBe('default');
  });

  it.each(['user', 'tenant', 'system'])(
    'uses an explicit %s language override instead of the browser language',
    async (source) => {
      await i18n.changeLanguage('zh-CN');
      useSettingsStore.setState({ language: 'zh' });
      settingsApi.getEffective.mockResolvedValueOnce({
        settings: { 'localization.language': 'en' },
        sources: { 'localization.language': source },
      });

      await useSettingsStore.getState().loadSettings();

      expect(useSettingsStore.getState().language).toBe('en');
      expect(useSettingsStore.getState().getSettingSource('localization.language')).toBe(source);
      expect(i18n.resolvedLanguage).toBe('en');
      expect(persistedLanguage()).toBe('en');
      expect(useSettingsStore.getState().settingsLoaded).toBe(true);
      expect(useSettingsStore.getState().settingsLoading).toBe(false);
    },
  );
});
