"""
Management command to train the land price prediction model.

Usage:
    python manage.py train_price_model
"""
from django.core.management.base import BaseCommand
from core.services.price_prediction import train_model


class Command(BaseCommand):
    help = 'Train the ML land price prediction ensemble model on the curated Kenya dataset'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Starting ensemble model training...'))

        try:
            metadata = train_model()

            self.stdout.write(self.style.SUCCESS(
                f"\n{'='*60}\n"
                f"  ENSEMBLE MODEL TRAINING COMPLETE\n"
                f"{'='*60}\n"
                f"  Model Version:  {metadata.get('model_version', 'N/A')}\n"
                f"  Records:        {metadata['n_records']}\n"
                f"  Features:       {metadata['n_features']}\n"
                f"  Counties:       {metadata['n_counties']}\n"
                f"  Constituencies: {metadata['n_constituencies']}\n"
                f"  Towns:          {metadata.get('n_towns', 'N/A')}\n"
                f"  RF R² Score:    {metadata['cv_r2_mean_rf']:.4f} "
                f"(+/- {metadata['cv_r2_std_rf']*2:.4f})\n"
                f"  GB R² Score:    {metadata['cv_r2_mean_gb']:.4f} "
                f"(+/- {metadata['cv_r2_std_gb']*2:.4f})\n"
                f"  Ensemble R²:    {metadata['cv_r2_mean']:.4f}\n"
                f"  Price Range:    KES {metadata['price_range']['min']:,} "
                f"- {metadata['price_range']['max']:,}/acre\n"
                f"  Trained At:     {metadata.get('trained_at', 'N/A')}\n"
                f"{'='*60}"
            ))

            self.stdout.write("\nFeature Importances (averaged):")
            avg_importances = metadata.get('feature_importances_avg', {})
            for feat, imp in sorted(
                avg_importances.items(),
                key=lambda x: x[1], reverse=True
            ):
                bar = '#' * int(imp * 50)
                self.stdout.write(f"  {feat:35s} {imp:.4f} {bar}")

            if metadata.get('feature_importances_rf'):
                self.stdout.write("\nRandomForest Importances:")
                for feat, imp in sorted(
                    metadata['feature_importances_rf'].items(),
                    key=lambda x: x[1], reverse=True
                ):
                    bar = '#' * int(imp * 50)
                    self.stdout.write(f"  {feat:35s} {imp:.4f} {bar}")

            if metadata.get('feature_importances_gb'):
                self.stdout.write("\nGradientBoosting Importances:")
                for feat, imp in sorted(
                    metadata['feature_importances_gb'].items(),
                    key=lambda x: x[1], reverse=True
                ):
                    bar = '#' * int(imp * 50)
                    self.stdout.write(f"  {feat:35s} {imp:.4f} {bar}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Training failed: {e}"))
            raise
