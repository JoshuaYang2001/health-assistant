import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import i18n from '../../i18n';
import { useSettingsStore } from '../../store/slices/settingsSlice';
import { AuthLanguageSelect } from './AuthLanguageSelect';

const updateOverride = vi.hoisted(() => vi.fn());
vi.mock('../../services/settingsService', () => ({
  settingsService: { updateOverride },
}));

describe('anonymous language selection', () => {
  beforeEach(async () => {
    cleanup();
    localStorage.clear();
    vi.clearAllMocks();
    await i18n.changeLanguage('en');
    useSettingsStore.setState(useSettingsStore.getInitialState(), true);
  });

  it('switches the login language without requesting authenticated settings writes', async () => {
    const user = userEvent.setup();
    const firstRender = render(<AuthLanguageSelect />);

    await user.selectOptions(screen.getByRole('combobox', { name: 'Language' }), 'zh');

    expect(screen.getByRole('combobox', { name: '语言' })).toHaveValue('zh');
    expect(useSettingsStore.getState().language).toBe('zh');
    expect(localStorage.getItem('i18nextLng')).toBe('zh');
    expect(updateOverride).not.toHaveBeenCalled();

    firstRender.unmount();
    render(<AuthLanguageSelect />);
    expect(screen.getByRole('combobox', { name: '语言' })).toHaveValue('zh');

    await user.selectOptions(screen.getByRole('combobox', { name: '语言' }), 'en');
    expect(screen.getByRole('combobox', { name: 'Language' })).toHaveValue('en');
    expect(updateOverride).not.toHaveBeenCalled();
  });
});
