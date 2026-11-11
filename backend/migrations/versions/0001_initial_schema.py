"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-11-07 15:10:20.829956
"""
from alembic import op
import sqlalchemy as sa


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('clinics',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('code', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('clinics', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_clinics_code'), ['code'], unique=True)

    op.create_table('model_versions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tag', sa.String(length=64), nullable=False),
    sa.Column('version', sa.String(length=20), nullable=False),
    sa.Column('data_source', sa.String(length=20), nullable=False),
    sa.Column('trained_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('card', sa.JSON(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tag')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=120), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('clinic_id', sa.Integer(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('failed_logins', sa.Integer(), nullable=False),
    sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_clinic_id'), ['clinic_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)
        batch_op.create_index(batch_op.f('ix_users_role'), ['role'], unique=False)

    op.create_table('appointments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=False),
    sa.Column('clinician_id', sa.Integer(), nullable=True),
    sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('reason', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['clinician_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('appointments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_appointments_patient_id'), ['patient_id'], unique=False)

    op.create_table('assessments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=12), nullable=False),
    sa.Column('urgency', sa.String(length=12), nullable=False),
    sa.Column('inputs', sa.JSON(), nullable=False),
    sa.Column('result', sa.JSON(), nullable=False),
    sa.Column('model_version', sa.String(length=64), nullable=True),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('reviewed_by', sa.Integer(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('clinician_summary', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('assessments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_assessments_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_assessments_patient_id'), ['patient_id'], unique=False)

    op.create_table('audit_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=True),
    sa.Column('clinic_id', sa.Integer(), nullable=True),
    sa.Column('action', sa.String(length=60), nullable=False),
    sa.Column('entity', sa.String(length=40), nullable=False),
    sa.Column('entity_id', sa.Integer(), nullable=True),
    sa.Column('ip', sa.String(length=45), nullable=True),
    sa.Column('detail', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_events_action'), ['action'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_events_actor_id'), ['actor_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_events_clinic_id'), ['clinic_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_events_created_at'), ['created_at'], unique=False)

    op.create_table('clinic_calibrations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('clinic_id', sa.Integer(), nullable=False),
    sa.Column('tier', sa.String(length=10), nullable=False),
    sa.Column('intercept', sa.Float(), nullable=False),
    sa.Column('slope', sa.Float(), nullable=False),
    sa.Column('method', sa.String(length=12), nullable=False),
    sa.Column('n', sa.Integer(), nullable=False),
    sa.Column('events', sa.Integer(), nullable=False),
    sa.Column('brier_before', sa.Float(), nullable=False),
    sa.Column('brier_after', sa.Float(), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('clinic_calibrations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_clinic_calibrations_clinic_id'), ['clinic_id'], unique=False)

    op.create_table('datasets',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('filename', sa.String(length=80), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('n_rows', sa.Integer(), nullable=False),
    sa.Column('columns', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('datasets', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_datasets_owner_id'), ['owner_id'], unique=False)

    op.create_table('measurements',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('value', sa.Float(), nullable=False),
    sa.Column('measured_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('measurements', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_measurements_kind'), ['kind'], unique=False)
        batch_op.create_index(batch_op.f('ix_measurements_measured_at'), ['measured_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_measurements_patient_id'), ['patient_id'], unique=False)

    op.create_table('patient_profiles',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('sex', sa.String(length=10), nullable=True),
    sa.Column('birth_year', sa.Integer(), nullable=True),
    sa.Column('height_cm', sa.Float(), nullable=True),
    sa.Column('smoking', sa.String(length=10), nullable=True),
    sa.Column('diabetes', sa.Boolean(), nullable=False),
    sa.Column('family_history', sa.Boolean(), nullable=False),
    sa.Column('conditions', sa.JSON(), nullable=False),
    sa.Column('activity_minutes', sa.Integer(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('clinical_notes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=False),
    sa.Column('author_id', sa.Integer(), nullable=False),
    sa.Column('assessment_id', sa.Integer(), nullable=True),
    sa.Column('body_encrypted', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('clinical_notes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_clinical_notes_patient_id'), ['patient_id'], unique=False)

    op.create_table('experiments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('dataset_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('kind', sa.String(length=24), nullable=False),
    sa.Column('provenance', sa.String(length=24), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('progress', sa.Float(), nullable=False),
    sa.Column('stage', sa.String(length=120), nullable=False),
    sa.Column('config', sa.JSON(), nullable=False),
    sa.Column('result', sa.JSON(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('experiments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_experiments_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_experiments_owner_id'), ['owner_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_experiments_status'), ['status'], unique=False)

    op.create_table('reports',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=True),
    sa.Column('assessment_id', sa.Integer(), nullable=True),
    sa.Column('experiment_id', sa.Integer(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['experiment_id'], ['experiments.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('reports')
    with op.batch_alter_table('experiments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_experiments_status'))
        batch_op.drop_index(batch_op.f('ix_experiments_owner_id'))
        batch_op.drop_index(batch_op.f('ix_experiments_created_at'))

    op.drop_table('experiments')
    with op.batch_alter_table('clinical_notes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_clinical_notes_patient_id'))

    op.drop_table('clinical_notes')
    op.drop_table('patient_profiles')
    with op.batch_alter_table('measurements', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_measurements_patient_id'))
        batch_op.drop_index(batch_op.f('ix_measurements_measured_at'))
        batch_op.drop_index(batch_op.f('ix_measurements_kind'))

    op.drop_table('measurements')
    with op.batch_alter_table('datasets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_datasets_owner_id'))

    op.drop_table('datasets')
    with op.batch_alter_table('clinic_calibrations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_clinic_calibrations_clinic_id'))

    op.drop_table('clinic_calibrations')
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_events_created_at'))
        batch_op.drop_index(batch_op.f('ix_audit_events_clinic_id'))
        batch_op.drop_index(batch_op.f('ix_audit_events_actor_id'))
        batch_op.drop_index(batch_op.f('ix_audit_events_action'))

    op.drop_table('audit_events')
    with op.batch_alter_table('assessments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_assessments_patient_id'))
        batch_op.drop_index(batch_op.f('ix_assessments_created_at'))

    op.drop_table('assessments')
    with op.batch_alter_table('appointments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_appointments_patient_id'))

    op.drop_table('appointments')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_role'))
        batch_op.drop_index(batch_op.f('ix_users_email'))
        batch_op.drop_index(batch_op.f('ix_users_clinic_id'))

    op.drop_table('users')
    op.drop_table('model_versions')
    with op.batch_alter_table('clinics', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_clinics_code'))

    op.drop_table('clinics')
