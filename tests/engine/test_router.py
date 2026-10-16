import unittest
from dataclasses import replace
from unittest.mock import patch

from tyrant.engine.router import (
    _chancellor_claims,
    _chancellor_truth,
    _claim_description,
    _correction_description,
    _president_claim,
    _president_claims,
    _president_truth,
    apply_action,
    get_legal_actions,
)
from tyrant.exceptions import TyrantError
from tyrant.models.action import (
    Action,
    NominateAction,
    VoteAction,
    PresidentDiscardAction,
    ChancellorEnactAction,
    ChancellorVetoAction,
    InvestigateLoyaltyAction,
    CallSpecialElectionAction,
    ExecutionAction,
    PolicyPeekAction,
    ClaimPolicyPeekAction,
    ClaimPresidentEnactAction,
    ClaimChancellorEnactAction,
    ClaimInvestigationAction,
    PresidentVetoResponseAction,
    SpeakAction,
    PassAction,
    CorrectClaimAction,
)
from tyrant.models.claim import (
    ChancellorEnactClaim,
    InvestigationClaim,
    PresidentEnactClaim,
)
from tyrant.models.election_tracker import ElectionTracker
from tyrant.models.enums import GamePhase, Party, PolicyTile, PresidentialPower, Vote
from tyrant.models.event import ClaimEvent
from tyrant.models.game_state import (
    GameState,
    cast_vote,
    claim_enact,
    create_game,
    nominate_chancellor,
    speak,
)
from tyrant.models.knowledge import (
    ChancellorReceiveKnowledge,
    PresidentDiscardKnowledge,
)


class TestGetLegalActionsNomination(unittest.TestCase):
    def test__get_legal_actions_nomination_immutability(self):
        """Ensure the output of _get_legal_actions_nomination is an immutable tuple."""
        state = create_game(tuple(range(5)))
        president = state.players[state.president_index]
        actions = get_legal_actions(state, president.uid)
        self.assertIsInstance(actions, tuple)

    def test__get_legal_actions_nomination_non_president(self):
        """Ensure every non-president player receives an empty tuple."""
        for player_count in range(5, 11):
            with self.subTest(player_count=player_count):
                state = create_game(tuple(range(player_count)))
                president_uid = state.players[state.president_index].uid
                for p in state.players:
                    if p.uid != president_uid:
                        actions = get_legal_actions(state, p.uid)
                        self.assertEqual(actions, tuple())

    def test__get_legal_actions_nomination_president_start(self):
        """Ensure that for every player count at the beginning of the game, everyone else is eligible for chancellorship."""
        for player_count in range(5, 11):
            with self.subTest(player_count=player_count):
                state = create_game(tuple(range(player_count)))
                president_uid = state.players[state.president_index].uid
                actions = get_legal_actions(state, president_uid)
                self.assertEqual(len(actions), player_count - 1)
                for action in actions:
                    self.assertTrue(isinstance(action, NominateAction))

    def test__get_legal_actions_nomination_president_5_player(self):
        """Ensure that in 5 player, the previous chancellor cannot be elected but previous president can."""
        state = create_game(tuple(range(5)))
        president_uid = state.players[state.president_index].uid
        other_uids = [p.uid for p in state.players if p.uid != president_uid]
        prev_chancellor = other_uids[0]
        prev_president = other_uids[1]

        state = replace(
            state,
            previous_chancellor=prev_chancellor,
            previous_president=prev_president,
        )
        actions = get_legal_actions(state, president_uid)
        [type(a).__name__ for a in actions]

        self.assertFalse(
            any(
                isinstance(a, NominateAction) and a.target_uid == prev_chancellor
                for a in actions
            )
        )
        self.assertTrue(
            any(
                isinstance(a, NominateAction) and a.target_uid == prev_president
                for a in actions
            )
        )
        self.assertEqual(len(actions), 3)

    def test__get_legal_actions_nomination_president_5_alive(self):
        """Ensure the previous chancellor cannot be elected but previous president can when only 5 players are alive."""
        for player_count in range(6, 11):
            with self.subTest(player_count=player_count):
                state = create_game(tuple(range(player_count)))
                new_players = list(state.players)
                killed = 0
                for i, p in enumerate(new_players):
                    if i != state.president_index and killed < (player_count - 5):
                        new_players[i] = replace(p, is_alive=False)
                        killed += 1
                state = replace(state, players=tuple(new_players))

                president_uid = state.players[state.president_index].uid
                alive_others = [
                    p.uid
                    for p in state.players
                    if p.is_alive and p.uid != president_uid
                ]
                prev_chancellor = alive_others[0]
                prev_president = alive_others[1]

                state = replace(
                    state,
                    previous_chancellor=prev_chancellor,
                    previous_president=prev_president,
                )
                actions = get_legal_actions(state, president_uid)
                [type(a).__name__ for a in actions]

                self.assertFalse(
                    any(
                        isinstance(a, NominateAction)
                        and a.target_uid == prev_chancellor
                        for a in actions
                    )
                )
                self.assertTrue(
                    any(
                        isinstance(a, NominateAction) and a.target_uid == prev_president
                        for a in actions
                    )
                )
                self.assertEqual(len(actions), 3)

    def test__get_legal_actions_nomination_president_6_10(self):
        """Ensure that neither the previous chancellor nor previous president can be elected."""
        for player_count in range(6, 11):
            with self.subTest(player_count=player_count):
                state = create_game(tuple(range(player_count)))
                president_uid = state.players[state.president_index].uid
                other_uids = [p.uid for p in state.players if p.uid != president_uid]
                prev_chancellor = other_uids[0]
                prev_president = other_uids[1]

                state = replace(
                    state,
                    previous_chancellor=prev_chancellor,
                    previous_president=prev_president,
                )
                actions = get_legal_actions(state, president_uid)
                [type(a).__name__ for a in actions]

                self.assertFalse(
                    any(
                        isinstance(a, NominateAction)
                        and a.target_uid == prev_chancellor
                        for a in actions
                    )
                )
                self.assertFalse(
                    any(
                        isinstance(a, NominateAction) and a.target_uid == prev_president
                        for a in actions
                    )
                )
                self.assertEqual(len(actions), player_count - 3)

    def test__get_legal_actions_invalid_uid(self):
        """Ensure TyrantError is raised for trying to get actions for an invalid uid."""
        state = create_game(tuple(range(5)))
        invalid_uid = 999
        with self.assertRaises(TyrantError):
            _ = get_legal_actions(state, invalid_uid)

    def test__get_legal_actions_nomination_excludes_dead_players(self):
        """Ensure a dead player is not included in the legal actions for nomination."""
        state = create_game(tuple(range(5)))
        president_uid = state.players[state.president_index].uid
        other_uids = [p.uid for p in state.players if p.uid != president_uid]
        dead_player_uid = other_uids[0]

        new_players = list(state.players)
        for i, p in enumerate(new_players):
            if p.uid == dead_player_uid:
                new_players[i] = replace(p, is_alive=False)
        state = replace(state, players=tuple(new_players))

        actions = get_legal_actions(state, president_uid)
        [type(a).__name__ for a in actions]

        self.assertFalse(
            any(
                isinstance(a, NominateAction) and a.target_uid == dead_player_uid
                for a in actions
            )
        )

    def test__get_legal_actions_nomination_excludes_self(self):
        """Ensure the active president is not included in the legal actions for nomination."""
        state = create_game(tuple(range(5)))
        president_uid = state.players[state.president_index].uid

        actions = get_legal_actions(state, president_uid)
        [type(a).__name__ for a in actions]

        self.assertFalse(
            any(
                isinstance(a, NominateAction) and a.target_uid == president_uid
                for a in actions
            )
        )

    def test__get_legal_actions_nomination_after_top_deck(self):
        """Ensure all alive players are eligible if term limits are cleared after a top deck."""
        state = create_game(tuple(range(5)))
        president_uid = state.players[state.president_index].uid
        other_uids = [p.uid for p in state.players if p.uid != president_uid]

        state = replace(
            state,
            previous_chancellor=other_uids[0],
            previous_president=other_uids[1],
            election_tracker=ElectionTracker(failed_elections=2),
        )

        state = nominate_chancellor(state, other_uids[2])
        for p in state.players:
            state = cast_vote(state, p.uid, Vote.NEIN)

        self.assertIsNone(state.previous_chancellor)
        self.assertIsNone(state.previous_president)

        new_president_uid = state.players[state.president_index].uid
        actions = get_legal_actions(state, new_president_uid)

        self.assertEqual(len(actions), 4)


class TestGetLegalActionsVoting(unittest.TestCase):
    def test__get_legal_actions_voting_immutability(self):
        """Ensure the output of _get_legal_actions_voting is an immutable tuple."""
        state = create_game(tuple(range(5)))
        state = replace(state, phase=GamePhase.VOTING)
        actions = get_legal_actions(state, state.players[0].uid)
        self.assertIsInstance(actions, tuple)

    def test__get_legal_actions_voting_alive_player(self):
        """Ensure an alive player who has not voted receives vote actions."""
        state = create_game(tuple(range(5)))
        state = replace(state, phase=GamePhase.VOTING)
        actions = get_legal_actions(state, state.players[0].uid)
        [type(a).__name__ for a in actions]
        self.assertTrue(
            any(isinstance(a, VoteAction) and a.vote == Vote.JA for a in actions)
        )
        self.assertTrue(
            any(isinstance(a, VoteAction) and a.vote == Vote.NEIN for a in actions)
        )
        self.assertEqual(len(actions), 2)

    def test__get_legal_actions_voting_dead_player(self):
        """Ensure a dead player receives an empty tuple of actions."""
        state = create_game(tuple(range(5)))
        state = replace(state, phase=GamePhase.VOTING)
        dead_uid = state.players[0].uid

        new_players = list(state.players)
        new_players[0] = replace(new_players[0], is_alive=False)
        state = replace(state, players=tuple(new_players))

        actions = get_legal_actions(state, dead_uid)
        self.assertEqual(actions, tuple())

    def test__get_legal_actions_voting_invalid_uid(self):
        """Ensure TyrantError is raised for trying to get actions for an invalid uid."""
        state = create_game(tuple(range(5)))
        state = replace(state, phase=GamePhase.VOTING)
        invalid_uid = 999
        with self.assertRaises(TyrantError):
            _ = get_legal_actions(state, invalid_uid)

    def test__get_legal_actions_voting_already_voted(self):
        """Ensure an alive player who has already cast a vote receives an empty tuple."""
        state = create_game(tuple(range(5)))
        state = replace(state, phase=GamePhase.VOTING)
        voter_uid = state.players[0].uid

        from tyrant.models.ballot_box import submit_vote

        new_ballot_box = submit_vote(state.ballot_box, voter_uid, Vote.JA)
        state = replace(state, ballot_box=new_ballot_box)

        actions = get_legal_actions(state, voter_uid)
        self.assertEqual(actions, tuple())


class TestGetLegalActionsPresidentDiscard(unittest.TestCase):
    def test__get_legal_actions_president_discard_immutability(self):
        """Ensure the output of _get_legal_actions_president_discard is an immutable tuple."""
        state = create_game(tuple(range(5)))
        state = replace(
            state,
            phase=GamePhase.PRESIDENT_DISCARD,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
        )
        actions = get_legal_actions(state, state.players[state.president_index].uid)
        self.assertIsInstance(actions, tuple)

    def test__get_legal_actions_president_discard_president_receives_actions(self):
        """Ensure the active president receives discard actions for each drawn policy."""
        state = create_game(tuple(range(5)))
        state = replace(
            state,
            phase=GamePhase.PRESIDENT_DISCARD,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
        )
        president_uid = state.players[state.president_index].uid
        actions = get_legal_actions(state, president_uid)

        self.assertEqual(len(actions), 3)
        self.assertTrue(
            isinstance(actions[0], PresidentDiscardAction)
            and actions[0].target_index == 0
        )
        self.assertEqual(actions[0].description, "Discard Fascist")
        self.assertTrue(
            isinstance(actions[1], PresidentDiscardAction)
            and actions[1].target_index == 1
        )
        self.assertEqual(actions[1].description, "Discard Liberal")
        self.assertTrue(
            isinstance(actions[2], PresidentDiscardAction)
            and actions[2].target_index == 2
        )
        self.assertEqual(actions[2].description, "Discard Fascist")

    def test__get_legal_actions_president_discard_non_president(self):
        """Ensure every non-president player receives an empty tuple."""
        state = create_game(tuple(range(5)))
        state = replace(
            state,
            phase=GamePhase.PRESIDENT_DISCARD,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
        )
        president_uid = state.players[state.president_index].uid

        for p in state.players:
            if p.uid != president_uid:
                actions = get_legal_actions(state, p.uid)
                self.assertEqual(actions, tuple())

    def test__get_legal_actions_president_discard_dead_player(self):
        """Ensure a dead player receives an empty tuple of actions."""
        state = create_game(tuple(range(5)))
        state = replace(
            state,
            phase=GamePhase.PRESIDENT_DISCARD,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
        )

        dead_uid = state.players[0].uid
        new_players = list(state.players)
        new_players[0] = replace(new_players[0], is_alive=False)
        state = replace(state, players=tuple(new_players))

        actions = get_legal_actions(state, dead_uid)
        self.assertEqual(actions, tuple())

    def test__get_legal_actions_president_discard_invalid_uid(self):
        """Ensure TyrantError is raised for trying to get actions for an invalid uid."""
        state = create_game(tuple(range(5)))
        state = replace(
            state,
            phase=GamePhase.PRESIDENT_DISCARD,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL, PolicyTile.FASCIST),
        )
        invalid_uid = 999
        with self.assertRaises(TyrantError):
            _ = get_legal_actions(state, invalid_uid)


class TestGetLegalActionsChancellorEnact(unittest.TestCase):
    def test__get_legal_actions_chancellor_enact_immutability(self):
        """Ensure the output is an immutable tuple."""
        state = create_game(tuple(range(5)))
        state = replace(
            state,
            phase=GamePhase.CHANCELLOR_ENACT,
            chancellor=state.players[1].uid,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        actions = get_legal_actions(state, state.players[1].uid)
        self.assertIsInstance(actions, tuple)

    def test__get_legal_actions_chancellor_enact_chancellor_receives_actions(self):
        """Ensure the active chancellor receives the exact enact actions for the drawn policies."""
        state = create_game(tuple(range(5)))
        chancellor_uid = state.players[1].uid
        state = replace(
            state,
            phase=GamePhase.CHANCELLOR_ENACT,
            chancellor=chancellor_uid,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        actions = get_legal_actions(state, chancellor_uid)
        self.assertEqual(len(actions), 2)
        self.assertTrue(
            isinstance(actions[0], ChancellorEnactAction)
            and actions[0].target_index == 0
        )
        self.assertEqual(actions[0].description, "Enact Fascist")
        self.assertTrue(
            isinstance(actions[1], ChancellorEnactAction)
            and actions[1].target_index == 1
        )
        self.assertEqual(actions[1].description, "Enact Liberal")

    def test__get_legal_actions_chancellor_enact_non_chancellor(self):
        """Ensure every other player (including the active president) receives an empty tuple."""
        state = create_game(tuple(range(5)))
        chancellor_uid = state.players[1].uid
        state = replace(
            state,
            phase=GamePhase.CHANCELLOR_ENACT,
            chancellor=chancellor_uid,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        for p in state.players:
            if p.uid != chancellor_uid:
                actions = get_legal_actions(state, p.uid)
                self.assertEqual(actions, tuple())

    def test__get_legal_actions_chancellor_enact_dead_player(self):
        """Ensure a dead player receives an empty tuple."""
        state = create_game(tuple(range(5)))
        dead_uid = state.players[1].uid
        new_players = list(state.players)
        new_players[1] = replace(new_players[1], is_alive=False)
        state = replace(
            state,
            players=tuple(new_players),
            phase=GamePhase.CHANCELLOR_ENACT,
            chancellor=dead_uid,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        actions = get_legal_actions(state, dead_uid)
        self.assertEqual(actions, tuple())

    def test__get_legal_actions_chancellor_enact_invalid_uid(self):
        """Ensure TyrantError is raised for trying to get actions for an invalid uid."""
        state = create_game(tuple(range(5)))
        state = replace(
            state,
            phase=GamePhase.CHANCELLOR_ENACT,
            chancellor=state.players[1].uid,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        invalid_uid = 999
        with self.assertRaises(TyrantError):
            _ = get_legal_actions(state, invalid_uid)

    def test__get_legal_actions_chancellor_enact_veto_locked(self):
        """Ensure the veto action is NOT in the returned tuple when veto_power_unlocked is False."""
        state = create_game(tuple(range(5)))
        chancellor_uid = state.players[1].uid
        state = replace(
            state,
            phase=GamePhase.CHANCELLOR_ENACT,
            chancellor=chancellor_uid,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        self.assertFalse(state.board.veto_power_unlocked)
        actions = get_legal_actions(state, chancellor_uid)
        [type(a).__name__ for a in actions]
        self.assertFalse(any(isinstance(a, ChancellorVetoAction) for a in actions))
        self.assertEqual(len(actions), 2)

    def test__get_legal_actions_chancellor_enact_veto_unlocked(self):
        """Ensure the veto action IS appended to the returned tuple when veto_power_unlocked is True."""
        state = create_game(tuple(range(5)))
        chancellor_uid = state.players[1].uid
        new_board = replace(state.board, fascist_played=5)
        state = replace(
            state,
            board=new_board,
            phase=GamePhase.CHANCELLOR_ENACT,
            chancellor=chancellor_uid,
            drawn_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL),
        )
        actions = get_legal_actions(state, chancellor_uid)
        [type(a).__name__ for a in actions]
        self.assertTrue(any(isinstance(a, ChancellorVetoAction) for a in actions))
        self.assertEqual(len(actions), 3)
        self.assertTrue(isinstance(actions[-1], ChancellorVetoAction))
        self.assertEqual(actions[-1].description, "Veto Policies")


class TestGetLegalActionsPresidentialPower(unittest.TestCase):
    def test__get_legal_actions_presidential_power_immutability(self):
        """Ensure the output of _get_legal_actions_presidential_power is an immutable tuple."""
        state = create_game(tuple(range(5)))
        state = replace(
            state,
            phase=GamePhase.PRESIDENTIAL_POWER,
            active_power=PresidentialPower.POLICY_PEEK,
        )
        actions = get_legal_actions(state, state.players[state.president_index].uid)
        self.assertIsInstance(actions, tuple)

    def test__get_legal_actions_presidential_power_non_president(self):
        """Ensure every non-president player receives an empty tuple."""
        state = create_game(tuple(range(5)))
        state = replace(
            state,
            phase=GamePhase.PRESIDENTIAL_POWER,
            active_power=PresidentialPower.POLICY_PEEK,
        )
        president_uid = state.players[state.president_index].uid
        for p in state.players:
            if p.uid != president_uid:
                actions = get_legal_actions(state, p.uid)
                self.assertEqual(actions, tuple())

    def test__get_legal_actions_presidential_power_policy_peek(self):
        """Ensure the president receives a peek action when active power is POLICY_PEEK."""
        state = create_game(tuple(range(5)))
        state = replace(
            state,
            phase=GamePhase.PRESIDENTIAL_POWER,
            active_power=PresidentialPower.POLICY_PEEK,
        )
        president_uid = state.players[state.president_index].uid
        actions = get_legal_actions(state, president_uid)
        self.assertEqual(len(actions), 1)
        self.assertTrue(isinstance(actions[0], PolicyPeekAction))

    def test__get_legal_actions_presidential_power_investigate_loyalty(self):
        """Ensure the president receives investigate actions for all other alive players."""
        state = create_game(tuple(range(5)))
        state = replace(
            state,
            phase=GamePhase.PRESIDENTIAL_POWER,
            active_power=PresidentialPower.INVESTIGATE_LOYALTY,
        )
        president_uid = state.players[state.president_index].uid
        actions = get_legal_actions(state, president_uid)
        self.assertEqual(len(actions), 4)
        for action in actions:
            self.assertTrue(isinstance(action, InvestigateLoyaltyAction))
            self.assertTrue(action.target_uid != president_uid)

    def test__get_legal_actions_presidential_power_investigate_loyalty_excludes_already_investigated(
        self,
    ):
        """Ensure already investigated players are excluded from investigate actions."""
        state = create_game(tuple(range(5)))
        president_uid = state.players[state.president_index].uid
        other_uids = [p.uid for p in state.players if p.uid != president_uid]
        state = replace(
            state,
            phase=GamePhase.PRESIDENTIAL_POWER,
            active_power=PresidentialPower.INVESTIGATE_LOYALTY,
            investigations=(other_uids[0],),
        )
        actions = get_legal_actions(state, president_uid)
        self.assertEqual(len(actions), 3)
        [type(a).__name__ for a in actions]
        self.assertFalse(
            any(
                isinstance(a, InvestigateLoyaltyAction)
                and a.target_uid == other_uids[0]
                for a in actions
            )
        )

    def test__get_legal_actions_presidential_power_call_special_election(self):
        """Ensure the president receives special election actions for all other alive players."""
        state = create_game(tuple(range(5)))
        state = replace(
            state,
            phase=GamePhase.PRESIDENTIAL_POWER,
            active_power=PresidentialPower.CALL_SPECIAL_ELECTION,
        )
        president_uid = state.players[state.president_index].uid
        actions = get_legal_actions(state, president_uid)
        self.assertEqual(len(actions), 4)
        for action in actions:
            self.assertTrue(isinstance(action, CallSpecialElectionAction))
            self.assertTrue(action.target_uid != president_uid)

    def test__get_legal_actions_presidential_power_execution(self):
        """Ensure the president receives execute actions for all other alive players."""
        state = create_game(tuple(range(5)))
        state = replace(
            state,
            phase=GamePhase.PRESIDENTIAL_POWER,
            active_power=PresidentialPower.EXECUTION,
        )
        president_uid = state.players[state.president_index].uid
        actions = get_legal_actions(state, president_uid)
        self.assertEqual(len(actions), 4)
        for action in actions:
            self.assertTrue(isinstance(action, ExecutionAction))
            self.assertTrue(action.target_uid != president_uid)

    def test__get_legal_actions_presidential_power_none_raises_error(self):
        """Ensure TyrantError is raised if the active power is NONE."""
        state = create_game(tuple(range(5)))
        state = replace(
            state,
            phase=GamePhase.PRESIDENTIAL_POWER,
            active_power=PresidentialPower.NONE,
        )
        president_uid = state.players[state.president_index].uid
        with self.assertRaises(TyrantError):
            _ = get_legal_actions(state, president_uid)


class TestGetLegalActionsInvestigation(unittest.TestCase):
    def test__get_legal_actions_investigation_immutability(self):
        """Ensure the output of _get_legal_actions_claim_investigation is an immutable tuple."""
        state = create_game(tuple(range(5)))
        state = replace(state, phase=GamePhase.CLAIM_INVESTIGATION)
        actions = get_legal_actions(state, state.players[state.president_index].uid)
        self.assertIsInstance(actions, tuple)

    def test__get_legal_actions_investigation_non_president(self):
        """Ensure every non-president player receives an empty tuple."""
        state = create_game(tuple(range(5)))
        state = replace(state, phase=GamePhase.CLAIM_INVESTIGATION)
        president_uid = state.players[state.president_index].uid
        for p in state.players:
            if p.uid != president_uid:
                actions = get_legal_actions(state, p.uid)
                self.assertEqual(actions, tuple())

    def test__get_legal_actions_investigation_president(self):
        """Ensure the president receives the claim investigation action."""
        state = create_game(tuple(range(5)))
        state = replace(state, phase=GamePhase.CLAIM_INVESTIGATION)
        president_uid = state.players[state.president_index].uid
        actions = get_legal_actions(state, president_uid)
        self.assertEqual(len(actions), 3)
        self.assertTrue(
            isinstance(actions[2], ClaimInvestigationAction)
            and actions[2].claim_party is None
        )

    def test__get_legal_actions_investigation_truth_first(self):
        """Verifies that the investigated player's real party is the first option and the only truthful one."""
        state = create_game(tuple(range(5)))
        state = replace(
            state,
            phase=GamePhase.CLAIM_INVESTIGATION,
            current_investigation_result=Party.FASCIST,
        )
        actions = get_legal_actions(state, state.players[state.president_index].uid)
        self.assertEqual(
            [a.claim_party for a in actions], [Party.FASCIST, Party.LIBERAL, None]
        )
        self.assertEqual(
            [a.description for a in actions[:2]],
            [
                "Claim the investigated player is a Fascist (matches what you saw).",
                "Claim the investigated player is a Liberal.",
            ],
        )


class TestClaimDescriptions(unittest.TestCase):
    def test__claim_description_immutability(self):
        """Verifies that _claim_description returns a new string and leaves its input unchanged."""
        claim = "you received fascist, liberal"
        result = _claim_description(claim, True)
        self.assertIsInstance(result, str)
        self.assertEqual(claim, "you received fascist, liberal")

    def test__claim_description_labels(self):
        """Verifies that _claim_description marks only the claim that matches what the player saw."""
        self.assertEqual(
            _claim_description("x", True), "Claim x (matches what you saw)."
        )
        self.assertEqual(_claim_description("x", False), "Claim x.")

    def test__president_claim_immutability(self):
        """Verifies that _president_claim returns a new string and leaves its input unchanged."""
        F, L = PolicyTile.FASCIST, PolicyTile.LIBERAL
        policies = (L, F, L)
        result = _president_claim(policies, L)
        self.assertIsInstance(result, str)
        self.assertEqual(policies, (L, F, L))

    def test__president_claim_implied_pass(self):
        """Verifies that _president_claim names the two policies the claim implies were passed."""
        F, L = PolicyTile.FASCIST, PolicyTile.LIBERAL
        self.assertEqual(
            _president_claim((L, F, L), L),
            "you drew fascist, liberal, liberal and discarded liberal, "
            "so you passed fascist, liberal",
        )


class TestGetLegalActionsPolicyPeek(unittest.TestCase):
    def test__get_legal_actions_policy_peek_immutability(self):
        """Ensure the output of _get_legal_actions_claim_peek is an immutable tuple."""
        state = create_game(tuple(range(5)))
        state = replace(state, phase=GamePhase.CLAIM_POLICY_PEEK)
        actions = get_legal_actions(state, state.players[state.president_index].uid)
        self.assertIsInstance(actions, tuple)

    def test__get_legal_actions_policy_peek_non_president(self):
        """Ensure every non-president player receives an empty tuple."""
        state = create_game(tuple(range(5)))
        state = replace(state, phase=GamePhase.CLAIM_POLICY_PEEK)
        president_uid = state.players[state.president_index].uid
        for p in state.players:
            if p.uid != president_uid:
                actions = get_legal_actions(state, p.uid)
                self.assertEqual(actions, tuple())

    def test__get_legal_actions_policy_peek_president(self):
        """Ensure the president receives the claim peek action."""
        state = create_game(tuple(range(5)))
        state = replace(state, phase=GamePhase.CLAIM_POLICY_PEEK)
        president_uid = state.players[state.president_index].uid
        actions = get_legal_actions(state, president_uid)
        self.assertEqual(
            len(actions), 9
        )  # 8 possible orderings for 3 cards + no response action
        self.assertTrue(
            isinstance(actions[0], ClaimPolicyPeekAction)
            and actions[0].claim_policies
            == (PolicyTile.LIBERAL, PolicyTile.LIBERAL, PolicyTile.LIBERAL)
        )

    def test__get_legal_actions_policy_peek_truth_first(self):
        """Verifies that the peeked policies in top-to-bottom order are the first option and the only truthful one."""
        F, L = PolicyTile.FASCIST, PolicyTile.LIBERAL
        state = create_game(tuple(range(5)))
        state = replace(
            state, phase=GamePhase.CLAIM_POLICY_PEEK, drawn_policies=(L, F, F)
        )
        actions = get_legal_actions(state, state.players[state.president_index].uid)
        self.assertEqual(len(actions), 9)
        self.assertEqual(actions[0].claim_policies, (L, F, F))
        self.assertEqual(
            actions[0].description,
            "Claim the top 3 policies are, from the top, liberal, fascist, fascist (matches what you saw).",
        )
        self.assertFalse(
            any("(matches what you saw)" in a.description for a in actions[1:])
        )

    def test__get_legal_actions_policy_peek_silence(self):
        """Ensure that player can choose to be silent when claiming."""
        state = create_game(tuple(range(5)))
        state = replace(state, phase=GamePhase.CLAIM_POLICY_PEEK)
        president_uid = state.players[state.president_index].uid
        actions = get_legal_actions(state, president_uid)
        self.assertTrue(
            isinstance(actions[-1], ClaimPolicyPeekAction)
            and actions[-1].claim_policies is None
        )


class TestGetLegalActionsPresidentVetoResponse(unittest.TestCase):
    def test__get_legal_actions_president_veto_response_immutability(self):
        """Ensure the output of _get_legal_actions_president_veto_response is an immutable tuple."""
        state = create_game(tuple(range(5)))
        state = replace(state, phase=GamePhase.PRESIDENT_VETO_RESPONSE)
        actions = get_legal_actions(state, state.players[state.president_index].uid)
        self.assertIsInstance(actions, tuple)

    def test__get_legal_actions_president_veto_response_non_president(self):
        """Ensure every non-president player receives an empty tuple."""
        state = create_game(tuple(range(5)))
        state = replace(state, phase=GamePhase.PRESIDENT_VETO_RESPONSE)
        president_uid = state.players[state.president_index].uid
        for p in state.players:
            if p.uid != president_uid:
                actions = get_legal_actions(state, p.uid)
                self.assertEqual(actions, tuple())

    def test__get_legal_actions_president_veto_response_president(self):
        """Ensure the president receives the accept and decline veto actions."""
        state = create_game(tuple(range(5)))
        state = replace(state, phase=GamePhase.PRESIDENT_VETO_RESPONSE)
        president_uid = state.players[state.president_index].uid
        actions = get_legal_actions(state, president_uid)
        self.assertEqual(len(actions), 2)
        [type(a).__name__ for a in actions]
        self.assertTrue(
            any(
                isinstance(a, PresidentVetoResponseAction) and a.approve
                for a in actions
            )
        )
        self.assertTrue(
            any(
                isinstance(a, PresidentVetoResponseAction) and not a.approve
                for a in actions
            )
        )


class TestGetLegalActionsSetup(unittest.TestCase):
    def test__get_legal_actions_setup(self):
        """Ensure every player receives an empty tuple during the SETUP phase."""
        state = create_game(tuple(range(5)))
        state = replace(state, phase=GamePhase.SETUP)
        for p in state.players:
            actions = get_legal_actions(state, p.uid)
            self.assertEqual(actions, tuple())


class TestGetLegalActionsGameOver(unittest.TestCase):
    def test__get_legal_actions_game_over(self):
        """Ensure every player receives an empty tuple during the GAME_OVER phase."""
        state = create_game(tuple(range(5)))
        state = replace(state, phase=GamePhase.GAME_OVER)
        for p in state.players:
            actions = get_legal_actions(state, p.uid)
            self.assertEqual(actions, tuple())


class TestGetLegalActionsDiscussion(unittest.TestCase):
    def _state(self):
        state = create_game(tuple(range(5)), discussion_enabled=True)
        return nominate_chancellor(state, state.players[1].uid)

    def test__get_legal_actions_discussion_immutability(self):
        """Ensure the output of _get_legal_actions_discussion is an immutable tuple."""
        state = self._state()
        actions = get_legal_actions(state, state.discussion.current_speaker)
        self.assertIsInstance(actions, tuple)

    def test__get_legal_actions_discussion_speaker(self):
        """Ensure the current speaker can speak or pass."""
        state = self._state()
        actions = get_legal_actions(state, state.discussion.current_speaker)
        self.assertEqual(len(actions), 2)
        self.assertIsInstance(actions[0], SpeakAction)
        self.assertIsInstance(actions[1], PassAction)

    def test__get_legal_actions_discussion_descriptions(self):
        """Ensure the speak option asks for something new and the pass option is suggested for repeats."""
        state = self._state()
        actions = get_legal_actions(state, state.discussion.current_speaker)
        self.assertEqual(
            [a.description for a in actions],
            [
                "Say something new to the table",
                "Stay silent (choose this if you would repeat an earlier point)",
            ],
        )

    def test__get_legal_actions_discussion_non_speaker(self):
        """Ensure every player other than the current speaker receives an empty tuple."""
        state = self._state()
        for p in state.players:
            if p.uid != state.discussion.current_speaker:
                self.assertEqual(get_legal_actions(state, p.uid), tuple())

    def test__get_legal_actions_discussion_dead_player(self):
        """Ensure a dead player receives an empty tuple during discussion."""
        state = self._state()
        speaker = state.discussion.current_speaker
        players = tuple(
            replace(p, is_alive=False) if p.uid == speaker else p for p in state.players
        )
        state = replace(state, players=players)
        self.assertEqual(get_legal_actions(state, speaker), tuple())


class TestApplyAction(unittest.TestCase):
    @patch("tyrant.engine.router.nominate_chancellor")
    def test_apply_action_nominate(self, mock_nominate):
        """Ensure nominate calls nominate_chancellor with the correct uid."""
        state = create_game(tuple(range(5)))
        action = NominateAction(description="", target_uid=3)
        apply_action(state, action, 0)
        mock_nominate.assert_called_once_with(state, 3)

    @patch("tyrant.engine.router.cast_vote")
    def test_apply_action_vote_ja(self, mock_vote):
        """Ensure vote_ja calls cast_vote with Vote.JA."""
        state = create_game(tuple(range(5)))
        action = VoteAction(description="", vote=Vote.JA)
        apply_action(state, action, 0)
        mock_vote.assert_called_once_with(state, 0, Vote.JA)

    @patch("tyrant.engine.router.cast_vote")
    def test_apply_action_vote_nein(self, mock_vote):
        """Ensure vote_nein calls cast_vote with Vote.NEIN."""
        state = create_game(tuple(range(5)))
        action = VoteAction(description="", vote=Vote.NEIN)
        apply_action(state, action, 0)
        mock_vote.assert_called_once_with(state, 0, Vote.NEIN)

    @patch("tyrant.engine.router.president_discard")
    def test_apply_action_discard(self, mock_discard):
        """Ensure discard calls president_discard with the correct index."""
        state = create_game(tuple(range(5)))
        action = PresidentDiscardAction(description="", target_index=1)
        apply_action(state, action, 0)
        mock_discard.assert_called_once_with(state, 1)

    @patch("tyrant.engine.router.chancellor_enact")
    def test_apply_action_enact(self, mock_enact):
        """Ensure enact calls chancellor_enact with the correct index."""
        state = create_game(tuple(range(5)))
        action = ChancellorEnactAction(description="", target_index=0)
        apply_action(state, action, 0)
        mock_enact.assert_called_once_with(state, 0)

    @patch("tyrant.engine.router.chancellor_veto")
    def test_apply_action_veto(self, mock_veto):
        """Ensure veto calls chancellor_veto."""
        state = create_game(tuple(range(5)))
        action = ChancellorVetoAction(description="")
        apply_action(state, action, 0)
        mock_veto.assert_called_once_with(state)

    @patch("tyrant.engine.router.investigate_loyalty")
    def test_apply_action_investigate(self, mock_investigate):
        """Ensure investigate calls investigate_loyalty with the correct uid."""
        state = create_game(tuple(range(5)))
        action = InvestigateLoyaltyAction(description="", target_uid=2)
        apply_action(state, action, 0)
        mock_investigate.assert_called_once_with(state, 2)

    @patch("tyrant.engine.router.call_special_election")
    def test_apply_action_special(self, mock_special):
        """Ensure special calls call_special_election with the correct uid."""
        state = create_game(tuple(range(5)))
        action = CallSpecialElectionAction(description="", target_uid=4)
        apply_action(state, action, 0)
        mock_special.assert_called_once_with(state, 4)

    @patch("tyrant.engine.router.execute_player")
    def test_apply_action_execute(self, mock_execute):
        """Ensure execute calls execute_player with the correct uid."""
        state = create_game(tuple(range(5)))
        action = ExecutionAction(description="", target_uid=1)
        apply_action(state, action, 0)
        mock_execute.assert_called_once_with(state, 1)

    @patch("tyrant.engine.router.policy_peek")
    def test_apply_action_peek(self, mock_peek):
        """Ensure peek calls policy_peek."""
        state = create_game(tuple(range(5)))
        action = PolicyPeekAction(description="")
        apply_action(state, action, 0)
        mock_peek.assert_called_once_with(state)

    @patch("tyrant.engine.router.claim_peek")
    def test_apply_action_claim_peek(self, mock_ack):
        """Ensure claim_peek calls claim_peek."""
        state = create_game(tuple(range(5)))
        action = ClaimPolicyPeekAction(
            description="",
            claim_policies=(PolicyTile.FASCIST, PolicyTile.FASCIST, PolicyTile.FASCIST),
        )
        apply_action(state, action, 0)
        from tyrant.models.claim import PeekClaim

        expected_claim = PeekClaim(
            uid=0, policies=(PolicyTile.FASCIST, PolicyTile.FASCIST, PolicyTile.FASCIST)
        )
        mock_ack.assert_called_once_with(state, expected_claim)

    @patch("tyrant.engine.router.claim_investigation")
    def test_apply_action_claim_investigation(self, mock_ack):
        """Ensure claim_investigation calls claim_investigation."""
        state = create_game(tuple(range(5)))
        action = ClaimInvestigationAction(description="", claim_party=Party.FASCIST)
        apply_action(state, action, 0)
        mock_ack.assert_called_once_with(
            state, InvestigationClaim(uid=0, party=Party.FASCIST)
        )

    @patch("tyrant.engine.router.president_veto_response")
    def test_apply_action_accept_veto(self, mock_veto_response):
        """Ensure accept_veto calls president_veto_response with True."""
        state = create_game(tuple(range(5)))
        action = PresidentVetoResponseAction(description="", approve=True)
        apply_action(state, action, 0)
        mock_veto_response.assert_called_once_with(state, True)

    @patch("tyrant.engine.router.president_veto_response")
    def test_apply_action_decline_veto(self, mock_veto_response):
        """Ensure decline_veto calls president_veto_response with False."""
        state = create_game(tuple(range(5)))
        action = PresidentVetoResponseAction(description="", approve=False)
        apply_action(state, action, 0)
        mock_veto_response.assert_called_once_with(state, False)

    @patch("tyrant.engine.router.speak")
    def test_apply_action_speak(self, mock_speak):
        """Ensure speak calls speak with the message text."""
        state = create_game(tuple(range(5)))
        action = SpeakAction(description="", message="I am liberal")
        apply_action(state, action, 2)
        mock_speak.assert_called_once_with(state, 2, "I am liberal")

    @patch("tyrant.engine.router.speak")
    def test_apply_action_pass(self, mock_speak):
        """Ensure pass calls speak with no text."""
        state = create_game(tuple(range(5)))
        action = PassAction(description="")
        apply_action(state, action, 2)
        mock_speak.assert_called_once_with(state, 2, None)

    def test_apply_action_invalid(self):
        """Ensure an invalid action ID raises a TyrantError."""
        state = create_game(tuple(range(5)))
        action = Action(description="fake")
        with self.assertRaises(TyrantError):
            apply_action(state, action, 0)


class TestGetLegalActionsEnactClaims(unittest.TestCase):
    def test_enact_claims_immutability(self):
        state = create_game(tuple(range(5)))
        president_uid = state.players[state.president_index].uid
        other_uid = next(p.uid for p in state.players if p.uid != president_uid)
        state = replace(
            state,
            phase=GamePhase.CLAIM_POLICIES,
            chancellor=other_uid,
            pending_president_enact_claim=True,
            pending_chancellor_enact_claim=True,
        )
        actions = get_legal_actions(state, president_uid)
        self.assertIsInstance(actions, tuple)

    def test_enact_claims_president(self):
        state = create_game(tuple(range(5)))
        president_uid = state.players[state.president_index].uid
        other_uid = next(p.uid for p in state.players if p.uid != president_uid)
        state = replace(
            state,
            phase=GamePhase.CLAIM_POLICIES,
            chancellor=other_uid,
            pending_president_enact_claim=True,
            pending_chancellor_enact_claim=True,
        )
        actions = get_legal_actions(state, president_uid)
        self.assertEqual(len(actions), 7)
        self.assertTrue(
            isinstance(actions[-1], ClaimPresidentEnactAction)
            and actions[-1].claim_policies is None
            and actions[-1].claim_discarded is None
        )

    def test_enact_claims_president_discard_options(self):
        """Verifies that each drawn-policy claim is offered once for every distinct discarded policy in it."""
        state = create_game(tuple(range(5)))
        president_uid = state.players[state.president_index].uid
        other_uid = next(p.uid for p in state.players if p.uid != president_uid)
        state = replace(
            state,
            phase=GamePhase.CLAIM_POLICIES,
            chancellor=other_uid,
            pending_president_enact_claim=True,
            pending_chancellor_enact_claim=True,
        )
        L, F = PolicyTile.LIBERAL, PolicyTile.FASCIST
        options = [
            (a.claim_policies, a.claim_discarded)
            for a in get_legal_actions(state, president_uid)[:-1]
        ]
        self.assertEqual(
            options,
            [
                ((F, F, F), F),
                ((F, F, L), F),
                ((F, F, L), L),
                ((F, L, L), F),
                ((F, L, L), L),
                ((L, L, L), L),
            ],
        )

    def test_enact_claims_chancellor(self):
        state = create_game(tuple(range(5)))
        president_uid = state.players[state.president_index].uid
        other_uid = next(p.uid for p in state.players if p.uid != president_uid)
        state = replace(
            state,
            phase=GamePhase.CLAIM_POLICIES,
            chancellor=other_uid,
            pending_president_enact_claim=True,
            pending_chancellor_enact_claim=True,
        )
        actions = get_legal_actions(state, other_uid)
        self.assertEqual(len(actions), 4)
        self.assertTrue(
            isinstance(actions[-1], ClaimChancellorEnactAction)
            and actions[-1].claim_policies is None
        )

    def test_enact_claims_non_involved(self):
        state = create_game(tuple(range(5)))
        president_uid = state.players[state.president_index].uid
        other_uid = next(p.uid for p in state.players if p.uid != president_uid)
        unrelated_uid = next(
            p.uid for p in state.players if p.uid not in (president_uid, other_uid)
        )
        state = replace(
            state,
            phase=GamePhase.CLAIM_POLICIES,
            chancellor=other_uid,
            pending_president_enact_claim=True,
            pending_chancellor_enact_claim=True,
        )
        actions = get_legal_actions(state, unrelated_uid)
        self.assertEqual(actions, tuple())

    def _claims_state(self):
        """Returns a claims-phase state where the president drew F, F, L, discarded F and the chancellor received F, L."""
        state = create_game(tuple(range(5)))
        president_uid = state.players[state.president_index].uid
        other_uid = next(p.uid for p in state.players if p.uid != president_uid)
        F, L = PolicyTile.FASCIST, PolicyTile.LIBERAL
        return replace(
            state,
            phase=GamePhase.CLAIM_POLICIES,
            chancellor=other_uid,
            pending_president_enact_claim=True,
            pending_chancellor_enact_claim=True,
            knowledge=(
                PresidentDiscardKnowledge(
                    uid=president_uid,
                    chancellor_uid=other_uid,
                    discarded=F,
                    passed=(L, F),
                ),
                ChancellorReceiveKnowledge(
                    uid=other_uid, president_uid=president_uid, policies=(L, F)
                ),
            ),
        )

    def test_enact_claims_president_truth_first(self):
        """Verifies that the president's truthful claim comes first and is the only one marked as matching what they saw."""
        state = self._claims_state()
        F, L = PolicyTile.FASCIST, PolicyTile.LIBERAL
        actions = get_legal_actions(state, state.players[state.president_index].uid)
        self.assertEqual(len(actions), 7)
        self.assertEqual(
            (actions[0].claim_policies, actions[0].claim_discarded), ((F, F, L), F)
        )
        self.assertEqual(
            actions[0].description,
            "Claim you drew fascist, fascist, liberal and discarded "
            "fascist, so you passed fascist, liberal (matches what you saw).",
        )
        self.assertEqual(
            ["(matches what you saw)" in a.description for a in actions].count(True),
            1,
        )
        self.assertTrue(
            all(a.description.startswith("Claim you drew ") for a in actions[1:-1])
        )

    def test_enact_claims_president_latest_knowledge(self):
        """Verifies that the president's truth comes from their latest discard."""
        state = self._claims_state()
        president_uid = state.players[state.president_index].uid
        L = PolicyTile.LIBERAL
        state = replace(
            state,
            knowledge=state.knowledge
            + (
                PresidentDiscardKnowledge(
                    uid=president_uid,
                    chancellor_uid=state.chancellor,
                    discarded=L,
                    passed=(L, L),
                ),
            ),
        )
        actions = get_legal_actions(state, president_uid)
        self.assertEqual(
            (actions[0].claim_policies, actions[0].claim_discarded), ((L, L, L), L)
        )

    def test_enact_claims_chancellor_truth_first(self):
        """Verifies that the chancellor's truthful claim comes first and is the only one marked as matching what they saw."""
        state = self._claims_state()
        F, L = PolicyTile.FASCIST, PolicyTile.LIBERAL
        actions = get_legal_actions(state, state.chancellor)
        self.assertEqual(len(actions), 4)
        self.assertEqual(actions[0].claim_policies, (F, L))
        self.assertEqual(
            actions[0].description,
            "Claim you received fascist, liberal (matches what you saw).",
        )
        self.assertEqual(
            [a.description for a in actions[1:3]],
            [
                "Claim you received fascist, fascist.",
                "Claim you received liberal, liberal.",
            ],
        )

    @patch("tyrant.engine.router.claim_enact")
    def test_apply_action_president_enact_claim(self, mock_claim):
        state = create_game(tuple(range(5)))
        president_uid = state.players[state.president_index].uid
        action = ClaimPresidentEnactAction(
            description="",
            claim_policies=(PolicyTile.FASCIST, PolicyTile.FASCIST, PolicyTile.FASCIST),
            claim_discarded=PolicyTile.FASCIST,
        )
        apply_action(state, action, president_uid)
        from tyrant.models.claim import PresidentEnactClaim

        mock_claim.assert_called_once_with(
            state,
            PresidentEnactClaim(
                uid=president_uid,
                policies=(PolicyTile.FASCIST, PolicyTile.FASCIST, PolicyTile.FASCIST),
                discarded=PolicyTile.FASCIST,
            ),
        )

    @patch("tyrant.engine.router.claim_enact")
    def test_apply_action_chancellor_enact_claim(self, mock_claim):
        state = create_game(tuple(range(5)))
        president_uid = state.players[state.president_index].uid
        other_uid = next(p.uid for p in state.players if p.uid != president_uid)
        action = ClaimChancellorEnactAction(
            description="", claim_policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL)
        )
        apply_action(state, action, other_uid)
        from tyrant.models.claim import ChancellorEnactClaim

        mock_claim.assert_called_once_with(
            state,
            ChancellorEnactClaim(
                uid=other_uid, policies=(PolicyTile.FASCIST, PolicyTile.LIBERAL)
            ),
        )


class TestGetLegalActionsCorrections(unittest.TestCase):
    F, L = PolicyTile.FASCIST, PolicyTile.LIBERAL

    def _discussion_state(self) -> GameState:
        """Returns the discussion after a president who drew F, F, L and discarded F lied about passing L, L, and the chancellor truthfully claimed F, L."""
        F, L = self.F, self.L
        state = create_game(tuple(range(5)), discussion_enabled=True)
        president_uid = state.players[state.president_index].uid
        chancellor_uid = state.players[(state.president_index + 1) % 5].uid
        state = replace(
            state,
            phase=GamePhase.CLAIM_POLICIES,
            chancellor=chancellor_uid,
            pending_president_enact_claim=True,
            pending_chancellor_enact_claim=True,
            knowledge=(
                PresidentDiscardKnowledge(
                    uid=president_uid,
                    chancellor_uid=chancellor_uid,
                    discarded=F,
                    passed=(L, F),
                ),
                ChancellorReceiveKnowledge(
                    uid=chancellor_uid, president_uid=president_uid, policies=(L, F)
                ),
            ),
        )
        state = claim_enact(
            state,
            PresidentEnactClaim(uid=president_uid, policies=(F, L, L), discarded=F),
        )
        return claim_enact(
            state, ChancellorEnactClaim(uid=chancellor_uid, policies=(F, L))
        )

    def _turn_of(self, state: GameState, uid: int) -> GameState:
        while state.discussion.current_speaker != uid:
            state = speak(state, state.discussion.current_speaker, None)
        return state

    def _government(self, state: GameState) -> tuple[int, int]:
        event = next(e for e in reversed(state.events) if isinstance(e, ClaimEvent))
        return event.president_uid, event.chancellor_uid

    def test__get_legal_actions_corrections_immutability(self):
        """Verifies that the corrections are returned as a tuple without changing the state."""
        state = self._discussion_state()
        president_uid, _ = self._government(state)
        state = self._turn_of(state, president_uid)
        events_before = state.events
        actions = get_legal_actions(state, president_uid)
        self.assertIsInstance(actions, tuple)
        self.assertEqual(state.events, events_before)

    def test__correction_description_immutability(self):
        """Verifies that _correction_description returns a new string and leaves its input unchanged."""
        claim = "you received fascist, liberal"
        self.assertIsInstance(_correction_description(claim, False), str)
        self.assertEqual(claim, "you received fascist, liberal")

    def test__president_truth_immutability(self):
        """Verifies that _president_truth leaves the state's knowledge unchanged."""
        state = self._discussion_state()
        knowledge_before = state.knowledge
        _president_truth(state, self._government(state)[0])
        self.assertEqual(state.knowledge, knowledge_before)

    def test__chancellor_truth_immutability(self):
        """Verifies that _chancellor_truth leaves the state's knowledge unchanged."""
        state = self._discussion_state()
        knowledge_before = state.knowledge
        _chancellor_truth(state, self._government(state)[1])
        self.assertEqual(state.knowledge, knowledge_before)

    def test__president_claims_immutability(self):
        """Verifies that _president_claims returns a new list for each call."""
        self.assertIsNot(_president_claims(None), _president_claims(None))
        self.assertEqual(len(_president_claims(None)), 6)

    def test__chancellor_claims_immutability(self):
        """Verifies that _chancellor_claims returns a new list for each call."""
        self.assertIsNot(_chancellor_claims(None), _chancellor_claims(None))
        self.assertEqual(len(_chancellor_claims(None)), 3)

    def test_president_corrections_follow_speak_and_pass(self):
        """Verifies that the president is offered every other non-decline claim after speaking and passing, the truth first."""
        F, L = self.F, self.L
        state = self._discussion_state()
        president_uid, _ = self._government(state)
        actions = get_legal_actions(self._turn_of(state, president_uid), president_uid)
        self.assertIsInstance(actions[0], SpeakAction)
        self.assertIsInstance(actions[1], PassAction)
        corrections = actions[2:]
        self.assertEqual(len(corrections), 5)
        self.assertTrue(all(isinstance(a, CorrectClaimAction) for a in corrections))
        self.assertEqual(
            corrections[0].claim,
            PresidentEnactClaim(uid=president_uid, policies=(F, F, L), discarded=F),
        )
        self.assertEqual(
            corrections[0].description,
            "Correct your claim: you drew fascist, fascist, liberal and "
            "discarded fascist, so you passed fascist, liberal (matches what you saw).",
        )
        self.assertTrue(
            all(
                a.description.startswith("Correct your claim: ")
                and "(matches what you saw)" not in a.description
                for a in corrections[1:]
            )
        )
        self.assertNotIn(
            ((F, L, L), F), [(a.claim.policies, a.claim.discarded) for a in corrections]
        )

    def test_chancellor_corrections_leave_out_current_claim(self):
        """Verifies that the chancellor is offered only the claims other than their current one."""
        state = self._discussion_state()
        _, chancellor_uid = self._government(state)
        actions = get_legal_actions(
            self._turn_of(state, chancellor_uid), chancellor_uid
        )
        corrections = actions[2:]
        self.assertEqual(len(corrections), 2)
        self.assertTrue(
            all(
                a.description.startswith("Correct your claim: ")
                and "(matches what you saw)" not in a.description
                for a in corrections
            )
        )
        self.assertNotIn((self.F, self.L), [a.claim.policies for a in corrections])

    def test_other_players_get_no_corrections(self):
        """Verifies that a player outside the government is only offered speaking and passing."""
        state = self._discussion_state()
        government = self._government(state)
        uid = next(p.uid for p in state.players if p.uid not in government)
        actions = get_legal_actions(self._turn_of(state, uid), uid)
        self.assertEqual(len(actions), 2)

    def test_apply_correction_records_correction(self):
        """Verifies that applying a correction records it as a correction claim event."""
        state = self._discussion_state()
        president_uid, _ = self._government(state)
        state = self._turn_of(state, president_uid)
        correction = get_legal_actions(state, president_uid)[2]
        new_state = apply_action(state, correction, president_uid)
        self.assertTrue(new_state.events[-1].correction)
        self.assertEqual(new_state.events[-1].claim, correction.claim)


if __name__ == "__main__":
    unittest.main()
