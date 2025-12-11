"""
Quality checker for detecting low-quality bug submissions
"""
from typing import Dict, List, Tuple
import re
import logging

logger = logging.getLogger(__name__)

class QualityChecker:
    """Checker for bug submission quality"""
    
    def __init__(
        self,
        min_description_length: int = 50,
        require_repro_steps: bool = True,
        require_logs: bool = False
    ):
        """
        Initialize quality checker
        
        Args:
            min_description_length: Minimum required description length
            require_repro_steps: Whether repro steps are required
            require_logs: Whether logs are required
        """
        self.min_description_length = min_description_length
        self.require_repro_steps = require_repro_steps
        self.require_logs = require_logs
    
    def check_quality(self, bug_data: Dict) -> Tuple[bool, List[str]]:
        """
        Check if bug submission meets quality standards
        
        Args:
            bug_data: Bug submission data
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        # Check title
        title = bug_data.get('title', '').strip()
        if not title:
            issues.append('missing_title')
        elif len(title) < 10:
            issues.append('title_too_short')
        elif self._is_generic_title(title):
            issues.append('generic_title')
        
        # Check description
        description = bug_data.get('description', '').strip()
        if not description:
            issues.append('missing_description')
        elif len(description) < self.min_description_length:
            issues.append('description_too_short')
        elif self._is_low_quality_text(description):
            issues.append('low_quality_description')
        
        # Check repro steps
        if self.require_repro_steps:
            repro_steps = bug_data.get('repro_steps', '').strip()
            if not repro_steps:
                issues.append('missing_repro_steps')
            elif len(repro_steps) < 20:
                issues.append('repro_steps_too_short')
        
        # Check logs
        if self.require_logs:
            logs = bug_data.get('logs', '').strip()
            if not logs:
                issues.append('missing_logs')
        
        # Check for required metadata
        if not bug_data.get('device'):
            issues.append('missing_device_info')
        
        if not bug_data.get('build_version'):
            issues.append('missing_build_version')
        
        if not bug_data.get('region'):
            issues.append('missing_region')
        
        # Valid if no critical issues
        is_valid = len(issues) == 0
        
        return is_valid, issues
    
    def _is_generic_title(self, title: str) -> bool:
        """Check if title is too generic"""
        generic_patterns = [
            r'^bug$',
            r'^error$',
            r'^issue$',
            r'^problem$',
            r'^help$',
            r'^test$',
            r'^broken$',
            r'^not working$',
            r'^doesn\'t work$',
            r'^crashes?$'
        ]
        
        title_lower = title.lower().strip()
        for pattern in generic_patterns:
            if re.match(pattern, title_lower):
                return True
        
        return False
    
    def _is_low_quality_text(self, text: str) -> bool:
        """Check if text appears to be low quality"""
        # Check for excessive repetition
        words = text.lower().split()
        if len(words) > 0:
            word_set = set(words)
            # If less than 30% unique words, likely spam/low quality
            if len(word_set) / len(words) < 0.3:
                return True
        
        # Check for all caps (shouting)
        if len(text) > 20 and text.isupper():
            return True
        
        # Check for excessive special characters
        special_char_ratio = sum(1 for c in text if not c.isalnum() and not c.isspace()) / len(text)
        if special_char_ratio > 0.3:
            return True
        
        return False
    
    def get_quality_score(self, bug_data: Dict) -> float:
        """
        Calculate a quality score from 0 to 1
        
        Args:
            bug_data: Bug submission data
            
        Returns:
            Quality score between 0 and 1
        """
        score = 1.0
        is_valid, issues = self.check_quality(bug_data)
        
        # Deduct points for each issue
        issue_penalties = {
            'missing_title': 0.3,
            'title_too_short': 0.1,
            'generic_title': 0.1,
            'missing_description': 0.3,
            'description_too_short': 0.15,
            'low_quality_description': 0.2,
            'missing_repro_steps': 0.2,
            'repro_steps_too_short': 0.1,
            'missing_logs': 0.1,
            'missing_device_info': 0.15,
            'missing_build_version': 0.15,
            'missing_region': 0.1
        }
        
        for issue in issues:
            penalty = issue_penalties.get(issue, 0.1)
            score -= penalty
        
        return max(0.0, score)
    
    def categorize_quality_issues(self, issues: List[str]) -> Dict[str, List[str]]:
        """
        Categorize quality issues by severity
        
        Args:
            issues: List of quality issues
            
        Returns:
            Dictionary with categorized issues
        """
        critical = []
        major = []
        minor = []
        
        critical_issues = {'missing_title', 'missing_description'}
        major_issues = {
            'description_too_short', 'low_quality_description',
            'missing_repro_steps', 'missing_device_info', 'missing_build_version'
        }
        
        for issue in issues:
            if issue in critical_issues:
                critical.append(issue)
            elif issue in major_issues:
                major.append(issue)
            else:
                minor.append(issue)
        
        return {
            'critical': critical,
            'major': major,
            'minor': minor
        }
