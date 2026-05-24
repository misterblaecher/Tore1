import 'package:flutter/material.dart';

import '../../ui/app_design_system.dart';

class ToreErrorState extends StatelessWidget {
  const ToreErrorState({super.key, required this.message, this.onRetry});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: ToreCard(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, color: AppColors.accentRed),
              const SizedBox(height: AppSpacing.sm),
              Text(message, textAlign: TextAlign.center),
              if (onRetry != null) ...[
                const SizedBox(height: AppSpacing.md),
                ToreButton.primary(
                    label: 'Réessayer',
                    icon: Icons.refresh,
                    onPressed: onRetry),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class ToreEmptyState extends StatelessWidget {
  const ToreEmptyState({super.key, required this.title, required this.message});

  final String title;
  final String message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: ToreCard(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.auto_awesome_motion_outlined,
                  color: AppColors.accentGold),
              const SizedBox(height: AppSpacing.sm),
              Text(title, style: AppTextStyles.sectionTitle),
              const SizedBox(height: AppSpacing.xs),
              Text(message,
                  textAlign: TextAlign.center, style: AppTextStyles.muted),
            ],
          ),
        ),
      ),
    );
  }
}

class ToreLoadingSkeleton extends StatelessWidget {
  const ToreLoadingSkeleton({super.key, this.lines = 3});

  final int lines;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        for (int i = 0; i < lines; i++)
          Container(
            height: 18,
            margin: const EdgeInsets.only(bottom: 10),
            decoration: BoxDecoration(
              color: Colors.white10,
              borderRadius: BorderRadius.circular(8),
            ),
          ),
      ],
    );
  }
}
