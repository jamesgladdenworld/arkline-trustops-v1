"""
Coordination Workflow - Routes questions to reviewers and manages notifications
Wraps ApprovalWorkflow to add routing, assignment, and notification capabilities
"""

import sqlite3
import logging
import json
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime
import re

logger = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    """Represents a routing decision"""
    question_id: int
    question_text: str
    target_team: str
    assigned_reviewer: str
    routing_rule: str
    confidence_score: float
    notification_level: str
    created_at: str


@dataclass
class Notification:
    """Represents a notification"""
    id: int
    recipient: str
    question_id: int
    message: str
    notification_type: str  # urgent, normal, info
    channel: str  # cli, email, slack, in_app
    sent_at: str
    read: bool


class NotificationManager:
    """Manages multi-channel notifications"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.channels = config.get('notification_channels', {})
    
    def send_notification(self, recipient: str, message: str, notification_type: str = "normal") -> bool:
        """
        Send notification through enabled channels
        
        Args:
            recipient: Email or username of recipient
            message: Notification message
            notification_type: urgent, normal, or info
            
        Returns:
            True if at least one channel succeeded
        """
        success = False
        
        # CLI notification (always enabled for V1)
        if self.channels.get('cli', {}).get('enabled', True):
            self._send_cli_notification(recipient, message, notification_type)
            success = True
        
        # Email notification
        if self.channels.get('email', {}).get('enabled', False):
            self._send_email_notification(recipient, message, notification_type)
            success = True
        
        # Slack notification
        if self.channels.get('slack', {}).get('enabled', False):
            self._send_slack_notification(recipient, message, notification_type)
            success = True
        
        # In-app notification
        if self.channels.get('in_app', {}).get('enabled', False):
            self._send_in_app_notification(recipient, message, notification_type)
            success = True
        
        return success
    
    def _send_cli_notification(self, recipient: str, message: str, notification_type: str):
        """Send CLI notification (print to console)"""
        prefix_map = {
            'urgent': '🚨',
            'normal': '📢',
            'info': 'ℹ️'
        }
        prefix = prefix_map.get(notification_type, '📢')
        
        print(f"\n{prefix} NOTIFICATION for {recipient}:")
        print(f"   {message}\n")
        logger.info(f"CLI notification sent to {recipient}")
    
    def _send_email_notification(self, recipient: str, message: str, notification_type: str):
        """Send email notification (placeholder for V1)"""
        logger.info(f"[EMAIL] Would send to {recipient}: {message}")
        # TODO: Implement email sending
    
    def _send_slack_notification(self, recipient: str, message: str, notification_type: str):
        """Send Slack notification (placeholder for V1)"""
        logger.info(f"[SLACK] Would send to {recipient}: {message}")
        # TODO: Implement Slack webhook
    
    def _send_in_app_notification(self, recipient: str, message: str, notification_type: str):
        """Store in-app notification (placeholder for V1)"""
        logger.info(f"[IN-APP] Would store for {recipient}: {message}")
        # TODO: Implement in-app notification storage


class RoutingEngine:
    """Routes questions to appropriate teams based on configurable rules"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.teams = config.get('teams', {})
        self.routing_rules = config.get('routing_rules', [])
        
        # Sort rules by priority
        self.routing_rules.sort(key=lambda r: r.get('priority', 999))
    
    def route_question(self, question: str, confidence_score: float) -> Tuple[str, str, str]:
        """
        Route a question to appropriate team
        
        Args:
            question: Question text
            confidence_score: AI confidence score (0-1)
            
        Returns:
            Tuple of (target_team, assigned_reviewer, routing_rule_name)
        """
        # Find matching rule
        for rule in self.routing_rules:
            if self._matches_rule(question, confidence_score, rule):
                target_team = rule.get('target_team', 'general_team')
                assigned_reviewer = self._select_reviewer(target_team)
                return (target_team, assigned_reviewer, rule.get('name', 'unknown'))
        
        # Fallback to general team
        return ('general_team', self._select_reviewer('general_team'), 'default_fallback')
    
    def _matches_rule(self, question: str, confidence_score: float, rule: Dict) -> bool:
        """Check if question matches routing rule"""
        conditions = rule.get('conditions', {})
        
        # Check confidence score range
        conf_min = conditions.get('confidence_min', 0)
        conf_max = conditions.get('confidence_max', 1.0)
        
        if not (conf_min <= confidence_score <= conf_max):
            return False
        
        # Check keywords
        keywords = conditions.get('keywords', [])
        if keywords:
            question_lower = question.lower()
            keyword_match = any(keyword.lower() in question_lower for keyword in keywords)
            if not keyword_match:
                return False
        
        return True
    
    def _select_reviewer(self, team_name: str) -> str:
        """Select a reviewer from the team (round-robin for V1)"""
        team = self.teams.get(team_name, {})
        members = team.get('members', [])
        
        if not members:
            logger.warning(f"No members in team {team_name}, using fallback")
            return "unassigned"
        
        # For V1, just return first member (can be enhanced with round-robin)
        return members[0]


class CoordinationWorkflow:
    """
    Coordination layer that wraps ApprovalWorkflow
    Handles routing, assignment, and notifications
    """
    
    def __init__(self, approval_workflow, config_path: str = "routing_config.json"):
        """
        Initialize Coordination Workflow
        
        Args:
            approval_workflow: ApprovalWorkflow instance to wrap
            config_path: Path to routing configuration file
        """
        self.approval_workflow = approval_workflow
        self.config_path = Path(config_path)
        
        # Load configuration
        self.config = self._load_config()
        
        # Initialize components
        self.routing_engine = RoutingEngine(self.config)
        self.notification_manager = NotificationManager(self.config)
        
        # Initialize database
        self._init_db()
    
    def _load_config(self) -> Dict:
        """Load routing configuration from JSON file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                logger.info(f"Loaded routing config from {self.config_path}")
                return config
            else:
                logger.warning(f"Config file not found: {self.config_path}")
                return self._get_default_config()
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """Get default configuration"""
        return {
            "teams": {
                "general_team": {
                    "description": "General reviewers",
                    "members": ["reviewer@company.com"],
                    "slack_channel": "#approvals",
                    "email_enabled": False
                }
            },
            "routing_rules": [
                {
                    "name": "default",
                    "priority": 999,
                    "conditions": {"keywords": [], "confidence_max": 1.0, "confidence_min": 0},
                    "target_team": "general_team",
                    "notification_level": "normal"
                }
            ],
            "notification_channels": {
                "cli": {"enabled": True, "format": "console"},
                "email": {"enabled": False},
                "slack": {"enabled": False},
                "in_app": {"enabled": False}
            }
        }
    
    def _init_db(self):
        """Initialize routing database"""
        conn = sqlite3.connect("coordination_workflow.db")
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS routing_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                target_team TEXT NOT NULL,
                assigned_reviewer TEXT NOT NULL,
                routing_rule TEXT NOT NULL,
                confidence_score REAL,
                notification_level TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient TEXT NOT NULL,
                question_id INTEGER,
                message TEXT NOT NULL,
                notification_type TEXT,
                channel TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read BOOLEAN DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Coordination workflow database initialized")
    
    def process_answer_with_routing(self, question: str, answer: str, 
                                   confidence_score: float, source_file: str) -> Dict:
        """
        Process an answer with routing and notification
        
        Args:
            question: Question text
            answer: AI-generated answer
            confidence_score: Confidence score (0-1)
            source_file: Source questionnaire file
            
        Returns:
            Dictionary with routing decision and draft ID
        """
        logger.info(f"\n{'='*60}")
        logger.info("COORDINATION WORKFLOW - Processing Answer")
        logger.info(f"{'='*60}\n")
        
        # Step 1: Route question
        logger.info("🔀 Routing question...")
        target_team, assigned_reviewer, routing_rule = self.routing_engine.route_question(
            question, confidence_score
        )
        logger.info(f"   ✅ Routed to: {target_team} ({assigned_reviewer})")
        logger.info(f"   📋 Rule: {routing_rule}\n")
        
        # Step 2: Create draft in approval workflow
        logger.info("📝 Creating approval draft...")
        draft_id = self.approval_workflow.create_draft(question, answer, confidence_score, source_file)
        logger.info(f"   ✅ Draft ID: {draft_id}\n")
        
        # Step 3: Log routing decision
        logger.info("📊 Logging routing decision...")
        routing_id = self._log_routing_decision(
            draft_id, question, target_team, assigned_reviewer, routing_rule, 
            confidence_score, "normal"
        )
        logger.info(f"   ✅ Routing ID: {routing_id}\n")
        
        # Step 4: Send notification
        logger.info("📢 Sending notification...")
        notification_msg = self._build_notification_message(
            question, confidence_score, target_team, routing_rule
        )
        self.notification_manager.send_notification(
            assigned_reviewer, notification_msg, "normal"
        )
        logger.info(f"   ✅ Notified: {assigned_reviewer}\n")
        
        return {
            "draft_id": draft_id,
            "routing_id": routing_id,
            "target_team": target_team,
            "assigned_reviewer": assigned_reviewer,
            "routing_rule": routing_rule,
            "confidence_score": confidence_score
        }
    
    def _log_routing_decision(self, question_id: int, question_text: str, 
                             target_team: str, assigned_reviewer: str, 
                             routing_rule: str, confidence_score: float,
                             notification_level: str) -> int:
        """Log routing decision to database"""
        try:
            conn = sqlite3.connect("coordination_workflow.db")
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO routing_decisions 
                (question_id, question_text, target_team, assigned_reviewer, 
                 routing_rule, confidence_score, notification_level)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (question_id, question_text, target_team, assigned_reviewer, 
                  routing_rule, confidence_score, notification_level))
            
            routing_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return routing_id
        except Exception as e:
            logger.error(f"Error logging routing decision: {e}")
            return None
    
    def _build_notification_message(self, question: str, confidence_score: float, 
                                   target_team: str, routing_rule: str) -> str:
        """Build notification message"""
        confidence_pct = confidence_score * 100
        return f"""
New question requires review:

Question: {question[:100]}...

Confidence: {confidence_pct:.0f}%
Team: {target_team}
Routing Rule: {routing_rule}

Please review and approve/reject in the approval workflow.
        """.strip()
    
    def get_routing_history(self, question_id: int = None) -> List[Dict]:
        """Get routing history"""
        try:
            conn = sqlite3.connect("coordination_workflow.db")
            cursor = conn.cursor()
            
            if question_id:
                cursor.execute('''
                    SELECT id, question_id, question_text, target_team, assigned_reviewer,
                           routing_rule, confidence_score, notification_level, created_at
                    FROM routing_decisions
                    WHERE question_id = ?
                    ORDER BY created_at DESC
                ''', (question_id,))
            else:
                cursor.execute('''
                    SELECT id, question_id, question_text, target_team, assigned_reviewer,
                           routing_rule, confidence_score, notification_level, created_at
                    FROM routing_decisions
                    ORDER BY created_at DESC
                    LIMIT 100
                ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    'id': row[0],
                    'question_id': row[1],
                    'question_text': row[2],
                    'target_team': row[3],
                    'assigned_reviewer': row[4],
                    'routing_rule': row[5],
                    'confidence_score': row[6],
                    'notification_level': row[7],
                    'created_at': row[8]
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error fetching routing history: {e}")
            return []
    
    def get_reviewer_queue(self, reviewer_email: str) -> List[Dict]:
        """Get pending questions assigned to a reviewer"""
        try:
            conn = sqlite3.connect("coordination_workflow.db")
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT rd.id, rd.question_id, rd.question_text, rd.confidence_score, 
                       rd.routing_rule, rd.created_at
                FROM routing_decisions rd
                WHERE rd.assigned_reviewer = ?
                AND rd.question_id NOT IN (
                    SELECT id FROM approval_records WHERE status IN ('approved', 'rejected')
                )
                ORDER BY rd.created_at ASC
            ''', (reviewer_email,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [
                {
                    'routing_id': row[0],
                    'question_id': row[1],
                    'question_text': row[2],
                    'confidence_score': row[3],
                    'routing_rule': row[4],
                    'created_at': row[5]
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error fetching reviewer queue: {e}")
            return []
    
    def export_routing_stats(self) -> Dict:
        """Export routing statistics"""
        try:
            conn = sqlite3.connect("coordination_workflow.db")
            cursor = conn.cursor()
            
            # Total routed
            cursor.execute('SELECT COUNT(*) FROM routing_decisions')
            total_routed = cursor.fetchone()[0]
            
            # By team
            cursor.execute('''
                SELECT target_team, COUNT(*) as count
                FROM routing_decisions
                GROUP BY target_team
            ''')
            by_team = {row[0]: row[1] for row in cursor.fetchall()}
            
            # By rule
            cursor.execute('''
                SELECT routing_rule, COUNT(*) as count
                FROM routing_decisions
                GROUP BY routing_rule
            ''')
            by_rule = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Average confidence by team
            cursor.execute('''
                SELECT target_team, AVG(confidence_score) as avg_conf
                FROM routing_decisions
                GROUP BY target_team
            ''')
            avg_conf_by_team = {row[0]: round(row[1], 2) for row in cursor.fetchall()}
            
            conn.close()
            
            return {
                'total_routed': total_routed,
                'by_team': by_team,
                'by_rule': by_rule,
                'average_confidence_by_team': avg_conf_by_team
            }
        except Exception as e:
            logger.error(f"Error exporting stats: {e}")
            return {}
