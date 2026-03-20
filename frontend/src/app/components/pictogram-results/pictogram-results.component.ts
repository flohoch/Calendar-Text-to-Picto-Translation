import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FieldTranslation } from '../../models/translation.model';

@Component({
  selector: 'app-pictogram-results',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="result-block" *ngIf="data">
      <div class="result-block-header">
        <span class="result-block-title">{{ label }}</span>
        <span class="result-original" *ngIf="data.originalText?.trim()">
          "{{ data.originalText }}"
        </span>
      </div>

      <ng-container *ngIf="data.originalText?.trim(); else emptyInput">
        <div class="picto-row" *ngIf="data.matches.length > 0; else noMatches">
          <div
            class="picto-card"
            *ngFor="let match of data.matches; trackBy: trackByMatch"
          >
            <img
              [src]="match.imageUrl"
              [alt]="match.matchedTerm"
              [title]="'ID: ' + match.pictogramId + ' — matched: &quot;' + match.matchedTerm + '&quot;'"
              loading="lazy"
            />
            <span class="picto-label">{{ match.matchedTerm }}</span>
            <span class="match-type" [ngClass]="'match-' + match.matchType.toLowerCase()">
              {{ match.matchType }}
            </span>
          </div>
        </div>

        <ng-template #noMatches>
          <p class="empty-field">No pictogram matches found</p>
        </ng-template>

        <div
          class="unmatched-tokens"
          *ngIf="data.unmatchedTokens && data.unmatchedTokens.length > 0"
        >
          ⚠ Unmatched:
          <span *ngFor="let token of data.unmatchedTokens">{{ token }}</span>
        </div>
      </ng-container>

      <ng-template #emptyInput>
        <p class="empty-field">No input provided</p>
      </ng-template>
    </div>
  `,
  styles: [
    `
      .result-block {
        background: #fff;
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
      }
      .result-block-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 0.75rem;
      }
      .result-block-title {
        font-weight: 700;
        font-size: 1.05rem;
        color: #16213e;
      }
      .result-original {
        font-size: 0.85rem;
        color: #777;
        font-style: italic;
      }
      .picto-row {
        display: flex;
        flex-wrap: wrap;
        gap: 1rem;
        align-items: flex-start;
      }
      .picto-card {
        display: flex;
        flex-direction: column;
        align-items: center;
        width: 110px;
        text-align: center;
      }
      .picto-card img {
        width: 90px;
        height: 90px;
        object-fit: contain;
        border: 2px solid #e8e8e8;
        border-radius: 8px;
        background: #fafafa;
        padding: 4px;
      }
      .picto-label {
        margin-top: 0.3rem;
        font-size: 0.78rem;
        color: #555;
        word-break: break-word;
      }
      .unmatched-tokens {
        margin-top: 0.75rem;
        font-size: 0.85rem;
        color: #b45309;
      }
      .unmatched-tokens span {
        background: #fff3cd;
        padding: 0.15rem 0.45rem;
        border-radius: 4px;
        margin-left: 0.3rem;
        font-weight: 500;
      }
      .empty-field {
        color: #aaa;
        font-style: italic;
        font-size: 0.9rem;
      }
    `,
  ],
})
export class PictogramResultsComponent {
  @Input() label = '';
  @Input() data: FieldTranslation | null = null;

  trackByMatch(_index: number, match: { pictogramId: number }): number {
    return match.pictogramId;
  }
}
