import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Language } from '../../models/translation.model';

@Component({
  selector: 'app-language-selector',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="lang-selector">
      <button
        class="lang-btn"
        [class.active]="value === 'de'"
        (click)="select('de')"
      >
        🇩🇪 Deutsch
      </button>
      <button
        class="lang-btn"
        [class.active]="value === 'en'"
        (click)="select('en')"
      >
        🇬🇧 English
      </button>
    </div>
  `,
  styles: [
    `
      .lang-selector {
        display: flex; gap: 0.5rem; margin-bottom: 1rem;
      }
      .lang-btn {
        padding: 0.5rem 1rem; border: 2px solid #ddd; background: #fff;
        border-radius: 8px; font-size: 0.95rem; cursor: pointer;
        transition: all 0.15s;
      }
      .lang-btn:hover { border-color: #4361ee; }
      .lang-btn.active {
        background: #4361ee; color: #fff; border-color: #4361ee;
      }
    `,
  ],
})
export class LanguageSelectorComponent {
  @Input() value: Language = 'de';
  @Output() valueChange = new EventEmitter<Language>();

  select(lang: Language) {
    this.valueChange.emit(lang);
  }
}
