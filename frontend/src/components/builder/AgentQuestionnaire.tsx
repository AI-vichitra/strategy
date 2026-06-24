'use client';
import { useState, useRef, useEffect } from 'react';
import styles from './AgentQuestionnaire.module.css';

export interface Question {
  id?: string;
  question: string;
  options: string[];
  multiSelect?: boolean;
  condition?: (answers: Record<string, string>) => boolean;
}

interface AgentQuestionnaireProps {
  questions: Question[];
  onComplete: (answers: Array<{ question: string; answer: string }>) => void;
  onDismiss: () => void;
}

export default function AgentQuestionnaire({
  questions,
  onComplete,
  onDismiss,
}: AgentQuestionnaireProps) {
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Array<{ question: string; answer: string }>>([]);
  const [selectedOptions, setSelectedOptions] = useState<string[]>([]);
  const [showInput, setShowInput] = useState(false);
  const [customText, setCustomText] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const answersMap = answers.reduce((acc, a) => {
    acc[a.question] = a.answer;
    return acc;
  }, {} as Record<string, string>);

  const visibleQuestions = questions.filter(q => !q.condition || q.condition(answersMap));

  const current = visibleQuestions[step];
  const total = visibleQuestions.length;
  const isLast = step === total - 1;
  const isMulti = current.multiSelect !== false;

  const commitAndAdvance = (answer: string) => {
    const updated = [...answers, { question: current.question, answer }];
    setAnswers(updated);
    setSelectedOptions([]);
    setShowInput(false);
    setCustomText('');
    if (isLast) {
      onComplete(updated);
    } else {
      setStep(step + 1);
    }
  };

  const handleToggle = (option: string) => {
    if (option.toLowerCase() === 'other' || option.toLowerCase() === 'others') {
      openSomethingElse();
      return;
    }
    if (!isMulti) {
      commitAndAdvance(option);
      return;
    }
    setSelectedOptions((prev) =>
      prev.includes(option) ? prev.filter((o) => o !== option) : [...prev, option]
    );
  };

  const handleMultiConfirm = () => {
    const parts = [...selectedOptions];
    if (customText.trim()) parts.push(customText.trim());
    if (parts.length === 0) return;
    commitAndAdvance(parts.join(', '));
  };

  const handleSkip = () => {
    setSelectedOptions([]);
    setShowInput(false);
    setCustomText('');
    if (isLast) {
      onComplete(answers);
    } else {
      setStep(step + 1);
    }
  };

  const handlePrev = () => {
    if (step > 0) {
      setAnswers(answers.slice(0, -1));
      setSelectedOptions([]);
      setShowInput(false);
      setCustomText('');
      setStep(step - 1);
    }
  };

  const handleNext = () => {
    if (step < total - 1) setStep(step + 1);
  };

  const openSomethingElse = () => {
    setShowInput(true);
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  // Auto-show input if no options are present
  useEffect(() => {
    if (visibleQuestions[step]?.options.length === 0) {
      setShowInput(true);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [step, visibleQuestions]);

  // Collapse the input if user blurs without typing anything
  const handleInputBlur = () => {
    if (!customText.trim() && current.options.length > 0) {
      setShowInput(false);
    }
  };

  const handleCustomSubmit = () => {
    const parts = [...selectedOptions];
    if (customText.trim()) parts.push(customText.trim());
    if (parts.length === 0) return;
    commitAndAdvance(parts.join(', '));
  };

  return (
    <div className={styles.wrapper}>
      {/* "Additional Questions" label bar */}
      <div className={styles.labelBar}>
        <span className={styles.labelBarIcon}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>
          </svg>
        </span>
        <span className={styles.labelBarText}>Additional Questions</span>
        <button className={styles.closeBtn} onClick={onDismiss} aria-label="Dismiss">&#x2715;</button>
      </div>

      {/* Question header */}
      <div className={styles.header}>
        <span className={styles.questionText}>{current.question}</span>
        <div className={styles.navGroup}>
          <button className={styles.navBtn} onClick={handlePrev} disabled={step === 0}>&#8249;</button>
          <span className={styles.stepIndicator}>{step + 1} of {total}</span>
          <button className={styles.navBtn} onClick={handleNext} disabled={isLast}>&#8250;</button>
        </div>
      </div>

      {/* Options — always multi-select checkboxes */}
      <div className={styles.optionsList}>
        {current.options.map((opt, i) => {
          const checked = selectedOptions.includes(opt);
          return (
            <button
              key={i}
              className={`${styles.optionRow} ${checked ? styles.optionSelected : ''}`}
              onClick={() => handleToggle(opt)}
            >
              <span className={`${styles.checkbox} ${checked ? styles.checkboxChecked : ''}`}>
                {checked && (
                  <svg width="10" height="10" viewBox="0 0 12 12" fill="none">
                    <polyline points="1.5,6 5,9.5 10.5,2.5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                )}
              </span>
              <span className={styles.optionLabel}>{opt}</span>
            </button>
          );
        })}

        {/* "Something else" row */}
        <div className={styles.skipRow}>
          {showInput ? (
            <div className={styles.customInputWrapper}>
              <input
                ref={inputRef}
                className={styles.customInput}
                placeholder="Add more details…"
                value={customText}
                onChange={(e) => setCustomText(e.target.value)}
                onBlur={handleInputBlur}
                onKeyDown={(e) => e.key === 'Enter' && handleCustomSubmit()}
              />
              <button
                className={styles.customSubmitBtn}
                onMouseDown={handleCustomSubmit}
                disabled={!customText.trim() && selectedOptions.length === 0}
              >
                &#8594;
              </button>
            </div>
          ) : (
            <>
              <span className={styles.pencilIcon} onClick={openSomethingElse}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
              </span>
              <span className={styles.skipLabel} onClick={openSomethingElse}>Something else</span>
            </>
          )}

          {selectedOptions.length > 0 && !showInput && (
            <button className={styles.confirmBtn} onClick={handleMultiConfirm}>
              Confirm ({selectedOptions.length})
            </button>
          )}
          {!showInput && (
            <button className={styles.skipBtn} onClick={handleSkip}>Skip</button>
          )}
        </div>
      </div>
    </div>
  );
}
