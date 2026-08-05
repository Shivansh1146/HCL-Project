"""001_initial_postgresql_schema

Revision ID: 001_initial_schema
Revises: None
Create Date: 2026-07-30 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Users Table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('github_id', sa.BigInteger(), nullable=False, unique=True),
        sa.Column('login', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('avatar_url', sa.Text(), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.Column('updated_at', sa.String(length=64), nullable=False),
        sa.Column('deleted_at', sa.String(length=64), nullable=True),
    )
    op.create_index('idx_users_github_id', 'users', ['github_id'])

    # 2. OAuth Tokens Table
    op.create_table(
        'oauth_tokens',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('access_token_enc', sa.Text(), nullable=False),
        sa.Column('token_type', sa.String(length=50), nullable=True, server_default='bearer'),
        sa.Column('scope', sa.Text(), nullable=True),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.Column('updated_at', sa.String(length=64), nullable=False),
    )

    # 3. Installations Table
    op.create_table(
        'installations',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('installation_id', sa.BigInteger(), nullable=False, unique=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('account_login', sa.String(length=255), nullable=False),
        sa.Column('account_id', sa.BigInteger(), nullable=False),
        sa.Column('account_type', sa.String(length=50), nullable=False, server_default='Organization'),
        sa.Column('target_type', sa.String(length=50), nullable=True),
        sa.Column('permissions_json', sa.Text(), nullable=True),
        sa.Column('events_json', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('suspended_at', sa.String(length=64), nullable=True),
        sa.Column('suspended_by', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.Column('updated_at', sa.String(length=64), nullable=False),
    )
    op.create_index('idx_inst_user', 'installations', ['user_id'])
    op.create_index('idx_inst_id', 'installations', ['installation_id'])

    # 4. Selected Repos Table
    op.create_table(
        'selected_repos',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('installation_id', sa.BigInteger(), nullable=False),
        sa.Column('repo_full_name', sa.String(length=255), nullable=False),
        sa.Column('enabled', sa.Integer(), server_default='1'),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.Column('updated_at', sa.String(length=64), nullable=False),
        sa.UniqueConstraint('user_id', 'repo_full_name', name='uq_user_repo')
    )
    op.create_index('idx_repos_enabled', 'selected_repos', ['enabled'])
    op.create_index('idx_repos_full_name', 'selected_repos', ['repo_full_name'])

    # 5. Organizations Table
    op.create_table(
        'organizations',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('github_org_id', sa.BigInteger(), nullable=False),
        sa.Column('login', sa.String(length=255), nullable=False),
        sa.Column('avatar_url', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.Column('updated_at', sa.String(length=64), nullable=False),
        sa.UniqueConstraint('user_id', 'github_org_id', name='uq_user_org')
    )
    op.create_index('idx_orgs_user', 'organizations', ['user_id'])

    # 6. Repositories Table
    op.create_table(
        'repositories',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('github_repo_id', sa.BigInteger(), nullable=False, unique=True),
        sa.Column('installation_id', sa.Integer(), sa.ForeignKey('installations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('owner_login', sa.String(length=255), nullable=False),
        sa.Column('private', sa.Integer(), server_default='0'),
        sa.Column('default_branch', sa.String(length=100), server_default='main'),
        sa.Column('language', sa.String(length=100), nullable=True),
        sa.Column('stargazers_count', sa.Integer(), server_default='0'),
        sa.Column('archived', sa.Integer(), server_default='0'),
        sa.Column('disabled', sa.Integer(), server_default='0'),
        sa.Column('fork', sa.Integer(), server_default='0'),
        sa.Column('open_pr_count', sa.Integer(), server_default='0'),
        sa.Column('reviewed_pr_count', sa.Integer(), server_default='0'),
        sa.Column('blocked_pr_count', sa.Integer(), server_default='0'),
        sa.Column('last_reviewed_at', sa.String(length=64), nullable=True),
        sa.Column('last_synced_at', sa.String(length=64), nullable=True),
        sa.Column('sync_status', sa.String(length=50), server_default='idle'),
        sa.Column('last_sync_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.String(length=64), nullable=False),
        sa.Column('updated_at', sa.String(length=64), nullable=False),
        sa.UniqueConstraint('installation_id', 'github_repo_id', name='uq_inst_repo')
    )
    op.create_index('idx_repos_inst', 'repositories', ['installation_id'])

    # 7. Audit Logs Table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('request_id', sa.String(length=255), nullable=True),
        sa.Column('trace_id', sa.String(length=255), nullable=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(length=255), nullable=False),
        sa.Column('entity_type', sa.String(length=100), nullable=True),
        sa.Column('entity_id', sa.String(length=255), nullable=True),
        sa.Column('severity', sa.String(length=50), server_default='INFO'),
        sa.Column('details_json', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=100), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.String(length=64), nullable=False),
    )
    op.create_index('idx_audit_user', 'audit_logs', ['user_id'])
    op.create_index('idx_audit_action', 'audit_logs', ['action'])
    op.create_index('idx_audit_created', 'audit_logs', ['created_at'])

    # 8. PRs Table
    op.create_table(
        'prs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('repo', sa.String(length=255), nullable=False),
        sa.Column('pr_number', sa.Integer(), nullable=False),
        sa.Column('reviewed_at', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('total_chunks', sa.Integer(), server_default='0'),
        sa.Column('high_count', sa.Integer(), server_default='0'),
        sa.Column('medium_count', sa.Integer(), server_default='0'),
        sa.Column('low_count', sa.Integer(), server_default='0'),
        sa.Column('decision_status', sa.String(length=50), nullable=True),
        sa.Column('decision_explanation', sa.Text(), nullable=True),
        sa.Column('coverage_percentage', sa.Float(), server_default='0.0'),
        sa.UniqueConstraint('repo', 'pr_number', name='uq_repo_pr')
    )
    op.create_index('idx_prs_repo', 'prs', ['repo'])
    op.create_index('idx_prs_decision', 'prs', ['decision_status'])

    # 9. Issues Table
    op.create_table(
        'issues',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('pr_id', sa.Integer(), sa.ForeignKey('prs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file', sa.Text(), nullable=False),
        sa.Column('line', sa.Integer(), nullable=False),
        sa.Column('severity', sa.String(length=50), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
    )
    op.create_index('idx_issues_pr_id', 'issues', ['pr_id'])
    op.create_index('idx_issues_severity', 'issues', ['severity'])


def downgrade() -> None:
    op.drop_table('issues')
    op.drop_table('prs')
    op.drop_table('audit_logs')
    op.drop_table('repositories')
    op.drop_table('organizations')
    op.drop_table('selected_repos')
    op.drop_table('installations')
    op.drop_table('oauth_tokens')
    op.drop_table('users')
