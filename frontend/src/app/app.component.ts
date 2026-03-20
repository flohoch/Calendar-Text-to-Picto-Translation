import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { EventFieldInputComponent } from './components/event-field-input/event-field-input.component';
import { PictogramResultsComponent } from './components/pictogram-results/pictogram-results.component';
import { TranslationService } from './services/translation.service';
import { TranslationResponse } from './models/translation.model';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, EventFieldInputComponent, PictogramResultsComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent {
  summary = '';
  location = '';
  participants = '';
  results: TranslationResponse | null = null;
  loading = false;
  error: string | null = null;

  constructor(private translationService: TranslationService) {}

  isAllEmpty(): boolean {
    return (
      !this.summary.trim() &&
      !this.location.trim() &&
      !this.participants.trim()
    );
  }

  onTranslate(): void {
    this.loading = true;
    this.error = null;
    this.results = null;

    this.translationService
      .translate({
        summary: this.summary,
        location: this.location,
        participants: this.participants,
      })
      .subscribe({
        next: (response) => {
          this.results = response;
          this.loading = false;
        },
        error: (err) => {
          this.error = err.message || 'Translation request failed';
          this.loading = false;
        },
      });
  }
}
