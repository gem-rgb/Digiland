"""
Management command to train the land price prediction model.

Usage:
    python manage.py train_price_model
"""
from django.core.management.base import BaseCommand
from core.services.price_prediction import train_model


class Command(BaseCommand):
    help = 'Train the ML land price prediction model on the curated Kenya dataset'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Starting model training...'))

        try:
            metadata = train_model()

            self.stdout.write(self.style.SUCCESS(
                f"\n{'='*60}\n"
                f"  MODEL TRAINING COMPLETE\n"
                f"{'='*60}\n"
                f"  Records:       {metadata['n_records']}\n"
                f"  Features:      {metadata['n_features']}\n"
                f"  Counties:      {metadata['n_counties']}\n"
                f"  Constituencies:{metadata['n_constituencies']}\n"
                f"  R² Score:      {metadata['cv_r2_mean']:.4f} "
                f"(+/- {metadata['cv_r2_std']*2:.4f})\n"
                f"  Price Range:   KES {metadata['price_range']['min']:,} "
                f"- {metadata['price_range']['max']:,}/acre\n"
                f"{'='*60}"
            ))

            self.stdout.write("\nFeature Importances:")
            for feat, imp in sorted(
                metadata['feature_importances'].items(),
                key=lambda x: x[1], reverse=True
            ):
                bar = '#' * int(imp * 50)
                self.stdout.write(f"  {feat:30s} {imp:.4f} {bar}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Training failed: {e}"))
            raise
