"""AgentActivity dataclass — records and formats a single simulation agent action."""

from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class AgentActivity:
    """Records a single agent action from the simulation."""

    platform: str           # twitter / reddit
    agent_id: int
    agent_name: str
    action_type: str        # CREATE_POST, LIKE_POST, etc.
    action_args: Dict[str, Any]
    round_num: int
    timestamp: str

    def to_episode_text(self) -> str:
        """
        Convert the activity to a natural-language text description for Zep.

        Uses a natural-language format so Zep can extract entities and relationships.
        No simulation-related prefix is added to avoid misleading the graph update.
        """
        # Dispatch to the action-specific description method
        action_descriptions = {
            "CREATE_POST": self._describe_create_post,
            "LIKE_POST": self._describe_like_post,
            "DISLIKE_POST": self._describe_dislike_post,
            "REPOST": self._describe_repost,
            "QUOTE_POST": self._describe_quote_post,
            "FOLLOW": self._describe_follow,
            "CREATE_COMMENT": self._describe_create_comment,
            "LIKE_COMMENT": self._describe_like_comment,
            "DISLIKE_COMMENT": self._describe_dislike_comment,
            "SEARCH_POSTS": self._describe_search,
            "SEARCH_USER": self._describe_search_user,
            "MUTE": self._describe_mute,
        }

        describe_func = action_descriptions.get(self.action_type, self._describe_generic)
        description = describe_func()

        # Return "agent_name: description" format with no simulation prefix
        return f"{self.agent_name}: {description}"

    def _describe_create_post(self) -> str:
        content = self.action_args.get("content", "")
        if content:
            return f"published a post: \"{content}\""
        return "published a post"

    def _describe_like_post(self) -> str:
        """Like a post — includes post content and author name."""
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")

        if post_content and post_author:
            return f"liked {post_author}'s post: \"{post_content}\""
        elif post_content:
            return f"liked a post: \"{post_content}\""
        elif post_author:
            return f"liked one of {post_author}'s posts"
        return "liked a post"

    def _describe_dislike_post(self) -> str:
        """Dislike a post — includes post content and author name."""
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")

        if post_content and post_author:
            return f"disliked {post_author}'s post: \"{post_content}\""
        elif post_content:
            return f"disliked a post: \"{post_content}\""
        elif post_author:
            return f"disliked one of {post_author}'s posts"
        return "disliked a post"

    def _describe_repost(self) -> str:
        """Repost — includes original post content and author name."""
        original_content = self.action_args.get("original_content", "")
        original_author = self.action_args.get("original_author_name", "")

        if original_content and original_author:
            return f"reposted {original_author}'s post: \"{original_content}\""
        elif original_content:
            return f"reposted a post: \"{original_content}\""
        elif original_author:
            return f"reposted one of {original_author}'s posts"
        return "reposted a post"

    def _describe_quote_post(self) -> str:
        """Quote post — includes original content, author, and the quote comment."""
        original_content = self.action_args.get("original_content", "")
        original_author = self.action_args.get("original_author_name", "")
        quote_content = self.action_args.get("quote_content", "") or self.action_args.get("content", "")

        base = ""
        if original_content and original_author:
            base = f"quoted {original_author}'s post \"{original_content}\""
        elif original_content:
            base = f"quoted a post \"{original_content}\""
        elif original_author:
            base = f"quoted one of {original_author}'s posts"
        else:
            base = "quoted a post"

        if quote_content:
            base += f", and commented: \"{quote_content}\""
        return base

    def _describe_follow(self) -> str:
        """Follow a user — includes the target username."""
        target_user_name = self.action_args.get("target_user_name", "")

        if target_user_name:
            return f"followed user \"{target_user_name}\""
        return "followed a user"

    def _describe_create_comment(self) -> str:
        """Post a comment — includes comment content and the post being replied to."""
        content = self.action_args.get("content", "")
        post_content = self.action_args.get("post_content", "")
        post_author = self.action_args.get("post_author_name", "")

        if content:
            if post_content and post_author:
                return f"commented on {post_author}'s post \"{post_content}\": \"{content}\""
            elif post_content:
                return f"commented on a post \"{post_content}\": \"{content}\""
            elif post_author:
                return f"commented on {post_author}'s post: \"{content}\""
            return f"commented: \"{content}\""
        return "posted a comment"

    def _describe_like_comment(self) -> str:
        """Like a comment — includes comment content and author name."""
        comment_content = self.action_args.get("comment_content", "")
        comment_author = self.action_args.get("comment_author_name", "")

        if comment_content and comment_author:
            return f"liked {comment_author}'s comment: \"{comment_content}\""
        elif comment_content:
            return f"liked a comment: \"{comment_content}\""
        elif comment_author:
            return f"liked one of {comment_author}'s comments"
        return "liked a comment"

    def _describe_dislike_comment(self) -> str:
        """Dislike a comment — includes comment content and author name."""
        comment_content = self.action_args.get("comment_content", "")
        comment_author = self.action_args.get("comment_author_name", "")

        if comment_content and comment_author:
            return f"disliked {comment_author}'s comment: \"{comment_content}\""
        elif comment_content:
            return f"disliked a comment: \"{comment_content}\""
        elif comment_author:
            return f"disliked one of {comment_author}'s comments"
        return "disliked a comment"

    def _describe_search(self) -> str:
        """Search posts — includes search query keyword."""
        query = self.action_args.get("query", "") or self.action_args.get("keyword", "")
        return f"searched for \"{query}\"" if query else "performed a search"

    def _describe_search_user(self) -> str:
        """Search users — includes search query keyword."""
        query = self.action_args.get("query", "") or self.action_args.get("username", "")
        return f"searched for user \"{query}\"" if query else "searched for a user"

    def _describe_mute(self) -> str:
        """Mute a user — includes the target username."""
        target_user_name = self.action_args.get("target_user_name", "")

        if target_user_name:
            return f"muted user \"{target_user_name}\""
        return "muted a user"

    def _describe_generic(self) -> str:
        # Generic fallback for unrecognised action types
        return f"performed action: {self.action_type}"
