import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { EventFieldInputComponent } from './components/event-field-input/event-field-input.component';
import { PictogramResultsComponent } from './components/pictogram-results/pictogram-results.component';
import { LanguageSelectorComponent } from './components/language-selector/language-selector.component';
import { EvaluationViewComponent } from './components/evaluation-view/evaluation-view.component';
import { TranslationService } from './services/translation.service';
import { Language, TranslationResponse } from './models/translation.model';

type Tab = 'translate' | 'evaluation';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    EventFieldInputComponent,
    PictogramResultsComponent,
    LanguageSelectorComponent,
    EvaluationViewComponent,
  ],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent {
  tab: Tab = 'translate';

  language: Language = 'de';
  summary = '';
  location = '';
  attendees = '';

  results: TranslationResponse | null = null;
  loading = false;
  error: string | null = null;

  constructor(private svc: TranslationService) {}

  isAllEmpty(): boolean {
    return (
      !this.summary.trim() &&
      !this.location.trim() &&
      !this.attendees.trim()
    );
  }

  setTab(t: Tab) {
    this.tab = t;
  }

  onTranslate() {
    this.loading = true;
    this.error = null;
    this.results = null;

    this.svc
      .translate({
        summary: this.summary,
        location: this.location,
        attendees: this.attendees,
        language: this.language,
      })
      .subscribe({
        next: (response) => {
          this.results = response;
          this.loading = false;
        },
        error: (err) => {
          this.error = err?.error?.detail || err.message;
          this.loading = false;
        },
      });
  }
}
