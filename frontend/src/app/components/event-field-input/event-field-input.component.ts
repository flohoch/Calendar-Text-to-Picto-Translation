import { Component, Input, Output, EventEmitter } from '@angular/core';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-event-field-input',
  standalone: true,
  imports: [FormsModule],
  template: `
    <div class="field-group">
      <label class="field-label">
        <span>{{ icon }}</span> {{ label }}
      </label>
      <input
        class="field-input"
        type="text"
        [placeholder]="placeholder"
        [ngModel]="value"
        (ngModelChange)="valueChange.emit($event)"
      />
    </div>
  `,
  styles: [
    `
      .field-group {
        margin-bottom: 1rem;
      }
      .field-label {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        font-weight: 600;
        font-size: 0.95rem;
        margin-bottom: 0.35rem;
        color: #333;
      }
      .field-input {
        width: 100%;
        padding: 0.65rem 0.85rem;
        border: 2px solid #ddd;
        border-radius: 8px;
        font-size: 1rem;
        transition: border-color 0.2s;
        box-sizing: border-box;
      }
      .field-input:focus {
        outline: none;
        border-color: #4361ee;
      }
    `,
  ],
})
export class EventFieldInputComponent {
  @Input() label = '';
  @Input() placeholder = '';
  @Input() icon = '';
  @Input() value = '';
  @Output() valueChange = new EventEmitter<string>();
}
