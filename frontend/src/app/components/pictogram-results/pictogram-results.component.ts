import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  AttendeeTranslation,
  FieldTranslation,
  PictogramMatch,
} from '../../models/translation.model';

@Component({
  selector: 'app-pictogram-results',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="result-block" *ngIf="data || attendees">
      <div class="result-block-header">
        <span class="result-block-title">{{ label }}</span>
        <span class="result-original" *ngIf="data?.originalText">
          "{{ data?.originalText }}"
        </span>
      </div>

      <!-- Single field (summary, location) -->
      <ng-container *ngIf="data && !attendees">
        <ng-container *ngIf="data.matches.length > 0; else noMatches">
          <div class="picto-row">
            <ng-container *ngFor="let m of data.matches">
              <ng-container *ngTemplateOutlet="card; context: { match: m }"></ng-container>
            </ng-container>
          </div>
        </ng-container>

        <div *ngIf="data.unmatchedTokens?.length" class="unmatched-tokens">
          ⚠ Unmatched:
          <span *ngFor="let t of data.unmatchedTokens">{{ t }}</span>
        </div>
      </ng-container>

      <!-- Attendees: each attendee gets its own row -->
      <ng-container *ngIf="attendees">
        <div *ngIf="attendees.length === 0" class="empty-field">No attendees</div>
        <div class="attendee-row" *ngFor="let att of attendees">
          <div class="attendee-label">{{ att.originalAttendee }}</div>
          <div class="picto-row">
            <ng-container *ngFor="let m of att.matches">
              <ng-container *ngTemplateOutlet="card; context: { match: m }"></ng-container>
            </ng-container>
            <span *ngIf="att.matches.length === 0" class="empty-field">No match</span>
          </div>
        </div>
      </ng-container>

      <ng-template #noMatches>
        <p class="empty-field">No pictogram matches found</p>
      </ng-template>

      <!-- Card template, shared between summary/location/attendees -->
      <ng-template #card let-match="match">
        <div class="picto-card">
          <img [src]="match.imageUrl" [alt]="match.matchedTerm" loading="lazy" />
          <span class="picto-label">{{ match.matchedTerm }}</span>
          <span class="picto-id">id {{ match.pictogramId }}</span>
          <span class="match-type" [ngClass]="'mt-' + match.matchType.toLowerCase()">
            {{ match.matchType }}
          </span>
          <span class="confidence">conf {{ match.confidence | number: '1.2-2' }}</span>
          <span class="original" *ngIf="match.originalInput && match.originalInput !== match.matchedTerm">
            from "{{ match.originalInput }}"
          </span>
        </div>
      </ng-template>
    </div>
  `,
  styles: [
    `
      .result-block {
        background: #fff; border-radius: 12px; padding: 1.25rem;
        margin-bottom: 1.25rem; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
      }
      .result-block-header {
        display: flex; align-items: center; justify-content: space-between;
        margin-bottom: 0.75rem;
      }
      .result-block-title { font-weight: 700; font-size: 1.05rem; color: #16213e; }
      .result-original { font-size: 0.85rem; color: #777; font-style: italic; }
      .picto-row { display: flex; flex-wrap: wrap; gap: 0.85rem; }
      .picto-card {
        display: flex; flex-direction: column; align-items: center;
        width: 130px; text-align: center; padding: 0.4rem;
        border: 1px solid #eee; border-radius: 8px;
      }
      .picto-card img {
        width: 90px; height: 90px; object-fit: contain;
        background: #fafafa; padding: 4px; border-radius: 6px;
      }
      .picto-label { margin-top: 0.3rem; font-size: 0.78rem; color: #555; word-break: break-word; }
      .picto-id { font-size: 0.7rem; color: #888; }
      .match-type {
        margin-top: 0.25rem; font-size: 0.62rem; font-weight: 700;
        padding: 0.1rem 0.4rem; border-radius: 4px; letter-spacing: 0.3px;
      }
      .mt-exact         { background: #d1fae5; color: #065f46; }
      .mt-sliding_window{ background: #c7f5e8; color: #035e54; }
      .mt-lexical_dict  { background: #e0f2fe; color: #075985; }
      .mt-disambiguated { background: #cffafe; color: #155e75; }
      .mt-personal_relationship { background: #fef9c3; color: #713f12; }
      .mt-lemma         { background: #dbeafe; color: #1e40af; }
      .mt-compound_split{ background: #ede9fe; color: #5b21b6; }
      .mt-synset        { background: #fef3c7; color: #92400e; }
      .mt-hypernym      { background: #fed7aa; color: #9a3412; }
      .mt-ner_person_fallback { background: #fce7f3; color: #9d174d; }
      .mt-generic_fallback    { background: #f3f4f6; color: #374151; }
      .confidence { font-size: 0.65rem; color: #888; margin-top: 0.15rem; }
      .original { font-size: 0.65rem; color: #aaa; margin-top: 0.1rem; font-style: italic; }
      .unmatched-tokens { margin-top: 0.75rem; font-size: 0.85rem; color: #b45309; }
      .unmatched-tokens span {
        background: #fff3cd; padding: 0.15rem 0.45rem; border-radius: 4px;
        margin-left: 0.3rem; font-weight: 500;
      }
      .empty-field { color: #aaa; font-style: italic; font-size: 0.9rem; }
      .attendee-row { margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px dashed #eee; }
      .attendee-row:first-child { border-top: none; padding-top: 0; }
      .attendee-label { font-weight: 600; font-size: 0.9rem; margin-bottom: 0.4rem; color: #333; }
    `,
  ],
})
export class PictogramResultsComponent {
  @Input() label = '';
  @Input() data: FieldTranslation | null = null;
  @Input() attendees: AttendeeTranslation[] | null = null;
}
