import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import commonEn from './locales/en/common.json';
import commonZh from './locales/zh/common.json';
import { getDateLocale } from './lib/dateLocale';
import { formatDistance } from 'date-fns';

function flattenStrings(value: unknown, prefix = ''): Record<string, string> {
  if (typeof value === 'string') return { [prefix]: value };
  if (typeof value !== 'object' || value === null) {
    throw new Error(`Invalid translation at ${prefix}`);
  }
  return Object.fromEntries(
    Object.entries(value).flatMap(([key, child]) =>
      Object.entries(flattenStrings(child, prefix ? `${prefix}.${key}` : key)),
    ),
  );
}

function placeholders(text: string): string[] {
  return (text.match(/{{.*?}}/g) ?? []).sort();
}

describe('Chinese language resources', () => {
  it('provides every English translation with all interpolation parameters intact', () => {
    const english = flattenStrings(commonEn);
    const chinese = flattenStrings(commonZh);

    expect(Object.keys(chinese).sort()).toEqual(Object.keys(english).sort());
    for (const [key, text] of Object.entries(english)) {
      expect(chinese[key].trim(), key).not.toBe('');
      expect(placeholders(chinese[key]), key).toEqual(placeholders(text));
    }
  });

  it('formats Chinese relative dates while preserving existing English and Greek locales', () => {
    const earlier = new Date(2026, 0, 1);
    const later = new Date(2026, 0, 2);

    expect(formatDistance(earlier, later, { locale: getDateLocale('zh-CN') })).toBe('1 天');
    expect(getDateLocale('en-US').code).toBe('en-US');
    expect(getDateLocale('el-GR').code).toBe('el');
  });
});

describe('browser language selection', () => {
  beforeEach(() => {
    vi.resetModules();
    localStorage.clear();
    vi.spyOn(navigator, 'language', 'get').mockReturnValue('zh-CN');
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['zh-CN', 'en-US']);
  });

  afterEach(() => vi.restoreAllMocks());

  it('loads Simplified Chinese for a Chinese browser and updates the document language', async () => {
    const { default: i18n } = await import('./i18n');

    expect(i18n.resolvedLanguage).toBe('zh');
    expect(i18n.t('common.settings')).toBe('设置');
    expect(document.documentElement.lang).toBe('zh-CN');
  });

  it('restores the manually selected language before using the browser preference', async () => {
    localStorage.setItem('i18nextLng', 'en');
    const { default: i18n } = await import('./i18n');

    expect(i18n.resolvedLanguage).toBe('en');
    expect(i18n.t('common.settings')).toBe('Settings');
    expect(document.documentElement.lang).toBe('en');

    await i18n.changeLanguage('zh');
    expect(localStorage.getItem('i18nextLng')).toBe('zh');
    expect(document.documentElement.lang).toBe('zh-CN');
    await i18n.changeLanguage('en');
    expect(localStorage.getItem('i18nextLng')).toBe('en');
    expect(document.documentElement.lang).toBe('en');
  });
});
