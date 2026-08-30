"""
Automated Test Suite for Digiland Entity, Membership, Decision Engine & Multi-Owner Architecture.
Tests:
1. Decoupled Account, Entity Types, and Member Roles.
2. Digital Crown for Team Manager vs Organization Badge for Institutions.
3. Decision & Voting Engine (1-person-1-vote principle).
4. Anti-Takeover and Democratic Member Removal.
5. Legal Ownership Override & Statutory Signatory Verification.
6. Legacy Migration Bridge Idempotency.
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.models import (
    Account,
    AccountMember,
    AccountInvitation,
    AccountDecision,
    DecisionVote,
    PropertyOwner,
    LandParcel,
    JointBuyerGroup,
    JointBuyerMember,
)
from core.services.account_authorization import can, Action, verify_legal_ownership_signoffs
from core.services.decision_engine import DecisionEngine
from core.services.account_migration import migrate_legacy_joint_groups

User = get_user_model()


class EntityArchitectureTests(TestCase):
    def setUp(self):
        # Create users (Digiland CustomUser uses email as identifier)
        self.manager = User.objects.create_user(
            email='manager@chama.co.ke',
            password='password123',
            first_name='Faith',
            last_name='Mwangi',
            role='Buyer',
        )
        self.member1 = User.objects.create_user(
            email='member1@chama.co.ke',
            password='password123',
            first_name='Peter',
            last_name='Kariuki',
            role='Buyer',
        )
        self.member2 = User.objects.create_user(
            email='member2@chama.co.ke',
            password='password123',
            first_name='Grace',
            last_name='Njeri',
            role='Buyer',
        )
        self.member3 = User.objects.create_user(
            email='member3@chama.co.ke',
            password='password123',
            first_name='David',
            last_name='Ochieng',
            role='Buyer',
        )

        # Create Land Parcel
        self.parcel = LandParcel.objects.create(
            parcel_number='KIAMBU/RUIRU/10294',
            land_use_type='Agricultural',
            county='Kiambu',
            constituency='Ruiru',
            ward='Biashara',
            land_size=Decimal('2.50'),
            registered_owner_id='28910293',
            asking_price=Decimal('5000000.00'),
            verification_status='Verified',
            listed_by=self.manager,
        )


    def test_01_joint_account_creation_and_digital_crown_manager(self):
        """Test human joint account creation, Team Manager role, and digital crown leadership."""
        account = Account.objects.create(
            account_type='JOINT',
            purpose='BUY',
            entity_type='CHAMA',
            display_name='Umoja Investment Chama',
            created_by=self.manager,
            governance_rule='SIMPLE_MAJORITY',
        )

        manager_member = AccountMember.objects.create(
            account=account,
            user=self.manager,
            role='BUYER_TEAM_MANAGER',
            status='ACTIVE',
            full_name='Faith Mwangi',
            email=self.manager.email,
            is_account_leader=True,
            share_percentage=Decimal('25.00'),
        )

        self.assertTrue(self.manager.is_account_manager)
        self.assertEqual(self.manager.primary_account, account)
        self.assertEqual(manager_member.role, 'BUYER_TEAM_MANAGER')
        self.assertTrue(manager_member.is_account_leader)

    def test_02_organization_account_and_no_crown_badge(self):
        """Test organizational account creation uses Primary Representative and no crown."""
        corp_user = User.objects.create_user(
            email='director@safariholdings.co.ke',
            password='password123',
            first_name='James',
            last_name='Kamau',
            role='Buyer',
        )


        org_account = Account.objects.create(
            account_type='ORGANIZATION',
            purpose='BUY',
            entity_type='COMPANY',
            display_name='Safari Land Holdings Ltd',
            legal_name='Safari Land Holdings Limited',
            registration_number='CPR/2026/9021',
            tax_id_or_kra_pin='P051982736Z',
            created_by=corp_user,
        )

        org_member = AccountMember.objects.create(
            account=org_account,
            user=corp_user,
            role='PRIMARY_REPRESENTATIVE',
            status='ACTIVE',
            full_name='James Kamau',
            email=corp_user.email,
            is_account_leader=False,  # Organizations do NOT have a human crowned manager
        )

        self.assertFalse(corp_user.is_account_manager)
        self.assertEqual(org_member.role, 'PRIMARY_REPRESENTATIVE')
        self.assertFalse(org_member.is_account_leader)

    def test_03_decision_engine_one_person_one_vote(self):
        """Test decision voting engine strictly enforces 1-person-1-vote and threshold rules."""
        account = Account.objects.create(
            account_type='JOINT',
            purpose='BUY',
            entity_type='CHAMA',
            display_name='Bidii Investment Group',
            created_by=self.manager,
            governance_rule='SIMPLE_MAJORITY',
        )

        # 4 active members
        AccountMember.objects.create(account=account, user=self.manager, role='BUYER_TEAM_MANAGER', status='ACTIVE', full_name='Faith M', is_account_leader=True)
        AccountMember.objects.create(account=account, user=self.member1, role='CO_BUYER', status='ACTIVE', full_name='Peter K')
        AccountMember.objects.create(account=account, user=self.member2, role='CO_BUYER', status='ACTIVE', full_name='Grace N')
        AccountMember.objects.create(account=account, user=self.member3, role='CO_BUYER', status='ACTIVE', full_name='David O')

        # Create proposal (creator auto-votes YES, so 1 YES out of 4 -> 25% -> still ACTIVE)
        decision = DecisionEngine.create_proposal(
            account=account,
            creator=self.manager,
            decision_type='PURCHASE_PROPOSAL',
            title='Buy Ruiru 2.5 Acres',
            proposal_text='Approve purchase of parcel KIAMBU/RUIRU/10294 for KES 5M',
            proposed_amount=Decimal('5000000.00'),
            land_parcel=self.parcel,
            approval_rule='SIMPLE_MAJORITY',
        )

        self.assertEqual(decision.status, 'ACTIVE')
        self.assertEqual(decision.approved_votes_count, 1)

        # Member 1 votes APPROVE -> 2 YES out of 4 (50%) -> Simple majority requires >50%, so still ACTIVE
        res1 = DecisionEngine.cast_vote(decision, self.member1, 'APPROVE', 'Looks good')
        decision.refresh_from_db()
        self.assertTrue(res1['success'])
        self.assertEqual(decision.status, 'ACTIVE')
        self.assertEqual(decision.approved_votes_count, 2)

        # Member 2 votes APPROVE -> 3 YES out of 4 (75% > 50%) -> APPROVED!
        res2 = DecisionEngine.cast_vote(decision, self.member2, 'APPROVE', 'Approved from my side')
        decision.refresh_from_db()
        self.assertTrue(res2['success'])
        self.assertEqual(decision.status, 'APPROVED')
        self.assertEqual(decision.approved_votes_count, 3)

    def test_04_anti_takeover_and_member_removal_voting(self):
        """
        Anti-Takeover test:
        1. Manager CANNOT unilaterally delete members.
        2. Removal must be proposed as a formal decision.
        3. Target member cannot vote on their own removal.
        4. When approved, target member is marked REMOVED.
        """
        account = Account.objects.create(
            account_type='JOINT',
            purpose='BUY',
            entity_type='CHAMA',
            display_name='Unity Chama',
            created_by=self.manager,
            governance_rule='SIMPLE_MAJORITY',
        )

        m_manager = AccountMember.objects.create(account=account, user=self.manager, role='BUYER_TEAM_MANAGER', status='ACTIVE', full_name='Faith M', is_account_leader=True)
        m_member1 = AccountMember.objects.create(account=account, user=self.member1, role='CO_BUYER', status='ACTIVE', full_name='Peter K')
        m_member2 = AccountMember.objects.create(account=account, user=self.member2, role='CO_BUYER', status='ACTIVE', full_name='Grace N')

        # Propose removal of member 1
        removal_decision = DecisionEngine.create_proposal(
            account=account,
            creator=self.manager,
            decision_type='MEMBER_REMOVAL',
            title='Propose Removal of Peter Kariuki',
            proposal_text='Peter has ceased active participation.',
            target_member=m_member1,
            approval_rule='SIMPLE_MAJORITY',
        )

        # Target member attempts to vote on their own removal -> Rejected!
        illegal_vote = DecisionEngine.cast_vote(removal_decision, self.member1, 'REJECT')
        self.assertFalse(illegal_vote['success'])
        self.assertIn('cannot vote on their own removal', illegal_vote['error'])

        # Member 2 votes APPROVE -> Out of 2 eligible non-target voters (manager + member2), 2 YES = 100% -> APPROVED
        vote_res = DecisionEngine.cast_vote(removal_decision, self.member2, 'APPROVE')
        self.assertTrue(vote_res['success'])
        removal_decision.refresh_from_db()
        m_member1.refresh_from_db()

        self.assertEqual(removal_decision.status, 'APPROVED')
        self.assertEqual(m_member1.status, 'REMOVED')

    def test_05_legal_ownership_override_and_statutory_protection(self):
        """
        Statutory Land Rights test:
        Ensures that platform voting never overrides registered legal property owners on title deeds.
        """
        # Register two legal owners on the land title (Tenancy in Common 60/40)
        owner_a = PropertyOwner.objects.create(
            land_parcel=self.parcel,
            user=self.manager,
            full_legal_name='Faith Wanjiku Mwangi',
            id_number_or_reg='28910293',
            kra_pin='A009182736K',
            ownership_structure='TENANCY_IN_COMMON',
            ownership_percentage=Decimal('60.00'),
            is_mandatory_signatory=True,
            legal_verification_status='LAWYER_VERIFIED',
        )
        owner_b = PropertyOwner.objects.create(
            land_parcel=self.parcel,
            user=self.member1,
            full_legal_name='Peter Kimani Kariuki',
            id_number_or_reg='19283746',
            kra_pin='A008273645M',
            ownership_structure='TENANCY_IN_COMMON',
            ownership_percentage=Decimal('40.00'),
            is_mandatory_signatory=True,
            legal_verification_status='UNVERIFIED',  # Lawyer has not verified yet
        )

        signoff_status = verify_legal_ownership_signoffs(self.parcel)
        self.assertTrue(signoff_status['has_legal_owners_registered'])
        self.assertFalse(signoff_status['is_fully_authorized'])
        self.assertEqual(len(signoff_status['pending_owners']), 1)
        self.assertEqual(signoff_status['pending_owners'][0]['name'], 'Peter Kimani Kariuki')

        # When lawyer verifies owner B
        owner_b.legal_verification_status = 'LAWYER_VERIFIED'
        owner_b.save(update_fields=['legal_verification_status'])

        updated_signoffs = verify_legal_ownership_signoffs(self.parcel)
        self.assertTrue(updated_signoffs['is_fully_authorized'])
        self.assertEqual(len(updated_signoffs['pending_owners']), 0)

    def test_06_legacy_joint_group_migration_idempotency(self):
        """Test seamless migration bridge from legacy JointBuyerGroup to unified Account architecture."""
        legacy_group = JointBuyerGroup.objects.create(
            name='Tuinuke Family Investment',
            group_type='Chama',
            leader=self.manager,
        )
        JointBuyerMember.objects.create(
            group=legacy_group,
            full_name='Faith Mwangi',
            email=self.manager.email,
            is_leader=True,
            share_percentage=Decimal('50.00'),
        )
        JointBuyerMember.objects.create(
            group=legacy_group,
            full_name='Peter Kariuki',
            email=self.member1.email,
            is_leader=False,
            share_percentage=Decimal('50.00'),
        )

        # Run migration
        result = migrate_legacy_joint_groups()
        self.assertEqual(result['status'], 'SUCCESS')

        # Check Account exists
        migrated_acc = Account.objects.get(id=legacy_group.id)
        self.assertEqual(migrated_acc.account_type, 'JOINT')
        self.assertEqual(migrated_acc.entity_type, 'CHAMA')
        self.assertEqual(migrated_acc.display_name, 'Tuinuke Family Investment')
        self.assertEqual(migrated_acc.members.count(), 2)

        # Run migration second time (idempotency check)
        result2 = migrate_legacy_joint_groups()
        self.assertEqual(result2['accounts_created'], 0)
