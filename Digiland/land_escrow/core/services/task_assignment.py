"""
Intelligent Task Assignment Service

This module provides AI-driven task assignment based on agent ratings,
usage patterns, work hours, and user reviews.
"""

from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from core.models import User as CoreUser, LandParcel, AgentRating, Transaction
import logging

logger = logging.getLogger(__name__)


class TaskAssignmentScorer:
    """
    Scores and recommends agents for task assignment based on:
    - Agent rating (verified reviews)
    - Task completion rate
    - Average response time
    - System usage frequency
    - Work hours
    - Parcel difficulty level
    """
    
    # Difficulty levels for parcels
    DIFFICULTY_EASY = 'easy'
    DIFFICULTY_MEDIUM = 'medium'
    DIFFICULTY_HARD = 'hard'
    
    # Minimum requirements for task assignment
    MIN_RATING_FOR_HARD_TASKS = Decimal('4.0')
    MIN_RATING_FOR_MEDIUM_TASKS = Decimal('3.0')
    MIN_RATING_FOR_EASY_TASKS = Decimal('2.0')
    
    # New agent grace period (14 days from creation)
    NEW_AGENT_THRESHOLD_DAYS = 14
    
    def __init__(self):
        self.today = timezone.now()
        
    def get_agent_score(self, agent, parcel_difficulty=DIFFICULTY_MEDIUM):
        """
        Calculate a comprehensive score for an agent based on:
        - Rating (40%)
        - Task completion rate (30%)
        - Usage frequency (20%)
        - Work hours consistency (10%)
        
        Returns: (score: float, details: dict)
        """
        if agent.role != 'Agent' or not agent.is_identity_verified or not agent.is_active:
            return 0, {'reason': 'Agent not verified or inactive'}
        
        # Check if agent is new
        days_since_creation = (self.today - agent.date_joined).days
        is_new_agent = days_since_creation < self.NEW_AGENT_THRESHOLD_DAYS
        
        # Get rating component (40% weight)
        rating_score, rating_details = self._calculate_rating_score(agent, is_new_agent)
        
        # Get completion rate (30% weight)
        completion_score, completion_details = self._calculate_completion_score(agent)
        
        # Get usage frequency score (20% weight)
        usage_score, usage_details = self._calculate_usage_score(agent)
        
        # Get work hours consistency score (10% weight)
        hours_score, hours_details = self._calculate_hours_score(agent)
        
        # Calculate weighted score
        total_score = (
            (rating_score * 0.40) +
            (completion_score * 0.30) +
            (usage_score * 0.20) +
            (hours_score * 0.10)
        )
        
        # Adjust for difficulty and agent experience
        difficulty_adjustment = self._get_difficulty_adjustment(
            agent, parcel_difficulty, is_new_agent
        )
        
        final_score = total_score * difficulty_adjustment
        
        details = {
            'is_new': is_new_agent,
            'days_since_creation': days_since_creation,
            'rating': rating_details,
            'completion': completion_details,
            'usage': usage_details,
            'hours': hours_details,
            'difficulty_adjustment': difficulty_adjustment,
            'final_score': float(final_score),
        }
        
        return final_score, details
    
    def _calculate_rating_score(self, agent, is_new_agent):
        """
        Calculate rating-based score (0-100).
        
        For new agents: start with 50, encourage early wins with easy tasks.
        For experienced agents: based on actual review ratings.
        """
        if is_new_agent:
            # New agents start with a moderate score to build experience
            return 50, {
                'average_rating': None,
                'review_count': 0,
                'status': 'new_agent_boost',
                'reason': 'New agent gets moderate score to build experience'
            }
        
        # Get all ratings for this agent
        ratings = AgentRating.objects.filter(agent=agent)
        
        if not ratings.exists():
            # No ratings yet - give moderate score
            return 60, {
                'average_rating': None,
                'review_count': 0,
                'status': 'no_ratings',
                'reason': 'No reviews yet, moderate score assigned'
            }
        
        avg_rating = ratings.aggregate(avg=Avg('rating'))['avg']
        rating_count = ratings.count()
        
        # Convert rating (1-5 scale) to score (0-100)
        if avg_rating:
            # Penalize if review count is very low (less than 3 reviews)
            if rating_count < 3:
                score = (avg_rating / 5.0) * 100 * 0.8  # 80% boost for low review count
            else:
                score = (avg_rating / 5.0) * 100
        else:
            score = 60  # Default if no rating
        
        return score, {
            'average_rating': float(avg_rating) if avg_rating else None,
            'review_count': rating_count,
            'status': 'rated',
        }
    
    def _calculate_completion_score(self, agent):
        """
        Calculate task completion rate (0-100).
        
        Completed parcels vs total assigned parcels.
        """
        completed = LandParcel.objects.filter(
            assigned_agent=agent,
            verification_status__in=['Verified', 'Fraudulent']
        ).count()
        
        total_assigned = LandParcel.objects.filter(assigned_agent=agent).count()
        
        if total_assigned == 0:
            return 75, {
                'completed': 0,
                'total': 0,
                'rate': None,
                'status': 'no_assignments'
            }
        
        completion_rate = completed / total_assigned
        score = completion_rate * 100
        
        return score, {
            'completed': completed,
            'total': total_assigned,
            'rate': float(completion_rate),
            'status': 'active'
        }
    
    def _calculate_usage_score(self, agent):
        """
        Calculate usage frequency score (0-100).
        
        Based on login frequency and activity in last 30 days.
        """
        thirty_days_ago = self.today - timedelta(days=30)
        
        # Check parcel verification activity in last 30 days
        recent_activity = LandParcel.objects.filter(
            assigned_agent=agent,
            ardhisasa_last_synced__gte=thirty_days_ago
        ).count()
        
        # Check transaction activity
        transaction_activity = Transaction.objects.filter(
            seller=agent,
            created_at__gte=thirty_days_ago
        ).count()
        
        total_recent_activity = recent_activity + transaction_activity
        
        # Score based on activity (assume 2-3 tasks per week is optimal)
        # That's ~8-12 tasks per month
        expected_activity = 10
        
        if total_recent_activity >= expected_activity:
            score = 100  # Highly active
        elif total_recent_activity >= expected_activity * 0.5:
            score = 80   # Moderately active
        elif total_recent_activity > 0:
            score = 60   # Some activity
        else:
            score = 30   # Inactive
        
        return score, {
            'recent_activity': total_recent_activity,
            'expected_activity': expected_activity,
            'status': 'active' if total_recent_activity > 0 else 'inactive'
        }
    
    def _calculate_hours_score(self, agent):
        """
        Calculate work hours consistency score (0-100).
        
        Based on transaction completion timing and verification patterns.
        """
        thirty_days_ago = self.today - timedelta(days=30)
        
        # Get completed transactions in last 30 days
        completed_tx = Transaction.objects.filter(
            seller=agent,
            status='Completed',
            updated_at__gte=thirty_days_ago
        ).count()
        
        # Get verified parcels in last 30 days
        verified_parcels = LandParcel.objects.filter(
            assigned_agent=agent,
            verification_status='Verified',
            ardhisasa_last_synced__gte=thirty_days_ago
        ).count()
        
        total_completions = completed_tx + verified_parcels
        
        # Consistency score based on steady work
        # More completions = higher consistency
        if total_completions >= 5:
            score = 100
        elif total_completions >= 3:
            score = 80
        elif total_completions >= 1:
            score = 60
        else:
            score = 40
        
        return score, {
            'completed_transactions': completed_tx,
            'verified_parcels': verified_parcels,
            'total_completions': total_completions,
            'status': 'consistent' if total_completions >= 3 else 'needs_improvement'
        }
    
    def _get_difficulty_adjustment(self, agent, difficulty, is_new_agent):
        """
        Adjust score based on task difficulty and agent experience.
        
        Returns multiplier (0.5 to 1.5):
        - New agents: penalized for hard tasks, rewarded for easy tasks
        - Experienced agents: can handle all difficulty levels
        """
        if is_new_agent:
            if difficulty == self.DIFFICULTY_EASY:
                return 1.2  # Encourage easy tasks for new agents
            elif difficulty == self.DIFFICULTY_MEDIUM:
                return 1.0  # Allow medium tasks
            else:  # HARD
                return 0.5  # Penalize hard tasks for new agents
        
        # For experienced agents, provide slight bonus for harder tasks
        if difficulty == self.DIFFICULTY_HARD:
            return 1.1
        elif difficulty == self.DIFFICULTY_EASY:
            return 0.9  # Slight penalty for very easy tasks (waste of capacity)
        else:
            return 1.0
    
    def recommend_agents(self, count=5, parcel_difficulty=DIFFICULTY_MEDIUM, exclude_agent_ids=None):
        """
        Recommend top N agents for task assignment.
        
        Returns: list of (agent, score, details) tuples, sorted by score descending
        """
        exclude_agent_ids = exclude_agent_ids or []
        
        # Get all verified, active agents
        agents = CoreUser.objects.filter(
            role='Agent',
            is_identity_verified=True,
            is_active=True
        ).exclude(id__in=exclude_agent_ids)
        
        scored_agents = []
        
        for agent in agents:
            score, details = self.get_agent_score(agent, parcel_difficulty)
            if score > 0:  # Only include agents with positive scores
                scored_agents.append((agent, score, details))
        
        # Sort by score (descending)
        scored_agents.sort(key=lambda x: x[1], reverse=True)
        
        return scored_agents[:count]
    
    def auto_assign_parcel(self, parcel):
        """
        Automatically assign a parcel to the best available agent.
        
        Returns: (agent, score, details) or (None, 0, {}) if no suitable agent found
        """
        # Determine parcel difficulty based on property characteristics
        # This is a simple heuristic - can be enhanced
        difficulty = self._determine_parcel_difficulty(parcel)
        
        # Get recommendations
        recommendations = self.recommend_agents(count=1, parcel_difficulty=difficulty)
        
        if recommendations:
            agent, score, details = recommendations[0]
            
            # Only auto-assign if score is above threshold
            if score >= 60:
                parcel.assigned_agent = agent
                parcel.save(update_fields=['assigned_agent'])
                logger.info(f"Auto-assigned parcel {parcel.parcel_number} to agent {agent.email} with score {score}")
                return agent, score, details
        
        logger.warning(f"Could not auto-assign parcel {parcel.parcel_number} - no suitable agents found")
        return None, 0, {'reason': 'No suitable agents available'}
    
    def _determine_parcel_difficulty(self, parcel):
        """
        Determine parcel difficulty based on characteristics.
        
        Factors:
        - Land price (higher = potentially more complex)
        - Land size (larger = potentially more complex)
        - Location (certain regions may be harder)
        """
        # Simple heuristic for now
        price = float(parcel.displayed_price or 0)
        
        if price > 2000000:  # > 2M KES
            return self.DIFFICULTY_HARD
        elif price > 500000:  # > 500K KES
            return self.DIFFICULTY_MEDIUM
        else:
            return self.DIFFICULTY_EASY
