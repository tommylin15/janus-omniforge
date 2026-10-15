"""Bounded fee repair inside the existing private Job, never through MCP.

The operator must bind an exact owner and ledger/profile checkpoint before apply.
Only counts and checkpoint metadata may cross the private runtime boundary.
"""
from decimal import Decimal

from services.api.models import BrokerProfileIn
from services.api.repository import ConflictError


def repair_owner_fees(repo, owner, *, expected_ledger_version, expected_profile_version, apply=False):
    profile = repo.broker_profile(owner)
    if profile['version'] != expected_profile_version or repo.latest_ledger_version(owner) != expected_ledger_version:
        raise ConflictError('fee repair checkpoint changed')
    if Decimal(str(profile.get('fee_discount_multiplier', '1'))) != Decimal('0.4'):
        if not apply:
            return {'status': 'profile_adjustment_required', 'ledger_mutated': False}
        profile = repo.save_broker_profile(owner, BrokerProfileIn(
            fee_discount_multiplier=Decimal('0.4'), minimum_fee=profile.get('minimum_fee', 20),
            cash_strategy=profile.get('cash_strategy', 'balanced'),
            declared_cash=profile.get('declared_cash'), cash_as_of=profile.get('cash_as_of'),
            expected_version=expected_profile_version,
        ), f'automatic-fee-discount-v1:{expected_profile_version}')
    preview = repo.reprice_ledger_fees(owner, expected_ledger_version=expected_ledger_version,
                                     expected_profile_version=profile['version'])
    result = preview
    if apply:
        result = repo.reprice_ledger_fees(owner, expected_ledger_version=expected_ledger_version,
                                        expected_profile_version=profile['version'], apply=True)
        check = repo.reprice_ledger_fees(owner, expected_ledger_version=result['ledger_version'],
                                       expected_profile_version=profile['version'])
        if check['corrections'] != 0:
            raise RuntimeError('fee repair readback mismatch')
    return {key: result[key] for key in ('status', 'effective_events', 'corrections',
            'based_on_ledger_version', 'broker_profile_version', 'ledger_version') if key in result}
