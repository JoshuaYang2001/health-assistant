import { useTranslation } from 'react-i18next';
import React, { useState, useEffect } from 'react';
import { updatePatient } from '../../../services/patientService';
import type { Patient } from '../../../types/patient';
import { SectionHeader, SetupField, SetupInput, SaveBar, type SectionProps } from './_shared';

const GENDERS = ['male', 'female', 'other', 'unknown'] as const;

/**
 * Demographics section: birth date, gender, MRN. Bound to `PUT /patients/:id`.
 * After save, calls `onSaved()` so the parent re-polls the checklist and the
 * `patient.birth_date` step flips green in-place (design D2 — no local
 * "completed" state; the backend is authoritative).
 */
export const DemographicsSection: React.FC<SectionProps> = ({ patient, onSaved }) => {
  const { t } = useTranslation();
  const [birthDate, setBirthDate] = useState(patient.birth_date ?? '');
  const [gender, setGender] = useState((patient.gender ?? 'unknown').toLowerCase());
  const [mrn, setMrn] = useState(patient.mrn ?? '');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Re-sync when the patient changes (e.g. after a parent checklist refresh).
  useEffect(() => {
    setBirthDate(patient.birth_date ?? '');
    setGender((patient.gender ?? 'unknown').toLowerCase());
    setMrn(patient.mrn ?? '');
  }, [patient.id, patient.birth_date, patient.gender, patient.mrn]);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      // null clears the field server-side (PatientUpdate uses Optional[date]).
      await updatePatient(patient.id, {
        birth_date: (birthDate || null) as Patient['birth_date'],
        gender: gender as Patient['gender'],
        mrn: (mrn || null) as Patient['mrn'],
      } as Partial<Patient>);
      setSaved(true);
      onSaved?.();
    } catch (err) {
      console.error('Failed to save demographics', err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section>
      <SectionHeader title={t('patient_form.steps.demographics')} description={t('patient_form.demographics_description')} />

      <div className="space-y-5">
        <SetupField label={t('patients.dob')} htmlFor="setup-demographics-dob">
          <SetupInput
            id="setup-demographics-dob"
            type="date"
            value={birthDate}
            onChange={(e) => { setBirthDate(e.target.value); setSaved(false); }}
          />
        </SetupField>

        <SetupField label={t('patients.gender')}>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {GENDERS.map((g) => (
              <button
                key={g}
                type="button"
                onClick={() => { setGender(g); setSaved(false); }}
                className={`px-3 py-2 rounded-xl text-sm font-medium border transition-all capitalize ${
                  gender === g
                    ? 'bg-blue-600 border-blue-600 text-white shadow-xs'
                    : 'bg-white dark:bg-dark-bg border-gray-200 dark:border-dark-border text-gray-600 dark:text-dark-muted hover:bg-gray-50'
                }`}
              >
                {t(`patients.gender_labels.${g}`)}
              </button>
            ))}
          </div>
        </SetupField>

        <SetupField label={t('patients.mrn')} hint={t('patient_form.mrn_hint')}>
          <SetupInput
            type="text"
            value={mrn}
            onChange={(e) => { setMrn(e.target.value); setSaved(false); }}
            placeholder={t('patient_form.mrn_placeholder')}
          />
        </SetupField>
      </div>

      <SaveBar onSave={handleSave} saving={saving} saved={saved} />
    </section>
  );
};

export default DemographicsSection;
