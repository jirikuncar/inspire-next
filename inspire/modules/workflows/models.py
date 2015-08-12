# -*- coding: utf-8 -*-
#
# This file is part of INSPIRE.
# Copyright (C) 2015 CERN.
#
# INSPIRE is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# INSPIRE is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with INSPIRE; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""Unified data model in workflow, based on Deposition model."""

from invenio.modules.deposit.models import (
    Deposition,
    Agent,
    DepositionDraft,
    SubmissionInformationPackage,
    DepositionStorage,
    DepositionFile,
)
from invenio.modules.workflows.registry import workflows


class Payload(Deposition):

    """Wrap a Deposition."""

    def __init__(self, workflow_object, type=None, user_id=None):
        self.files = []
        self.drafts = {}
        self.type = self.get_type(type)
        self.title = ''
        self.sips = []
        super(Payload, self).__init__(workflow_object, type, user_id)

    @classmethod
    def get_type(self, type_or_id):
        """Get type."""
        return workflows.get(type_or_id)

    @classmethod
    def create(cls, user=None, type=None, workflow_object=None):
        """
        Create a new deposition object.

        To persist the deposition, you must call save() on the created object.
        If no type is defined, the default deposition type will be assigned.

        @param user: The owner of the deposition
        @param type: Deposition type identifier.
        """
        if user is not None:
            user = user.get_id()

        if workflow_object:
            sip = SubmissionInformationPackage(metadata=workflow_object.data)
            workflow_object.data = {
                "sips": [sip.__getstate__()],
                "files": [],
                "title": "",
                "drafts": {},
                "type": type,
            }
            workflow_object.set_data(workflow_object.data)
            workflow_object.save()

        # Note: it is correct to pass 'type' and not 't' below to constructor.
        obj = cls(workflow_object=workflow_object, type=type, user_id=user)
        return obj

    def __setstate__(self, state):
        """Deserialize deposition from state stored in BibWorkflowObject."""
        self.type = self.get_type(state['type'])
        self.title = state['title']
        self.files = [
            DepositionFile.factory(
                f_state,
                uuid=f_state['id'],
                backend=DepositionStorage(self.id),
            )
            for f_state in state['files']
        ]
        self.drafts = dict(
            [(d_id, DepositionDraft.factory(d_state, d_id,
                                            deposition_ref=self))
             for d_id, d_state in state['drafts'].items()]
        )
        self.sips = [
            SubmissionInformationPackage.factory(s_state, uuid=s_state['id'])
            for s_state in state.get('sips', [])
        ]

    def __getstate__(self):
        """Serialize deposition state for storing in the BibWorkflowObject."""
        # The bibworkflow object id and owner is implicit, as the Deposition
        # object only wraps the data attribute of a BibWorkflowObject.

        return dict(
            type=self.type.__name__,
            title=self.title,
            files=[f.__getstate__() for f in self.files],
            drafts=dict(
                [(d_id, d.__getstate__()) for d_id, d in self.drafts.items()]
            ),
            sips=[f.__getstate__() for f in self.sips],
        )

    def prepare_sip(self, from_request_context=False):
        sip = self.get_latest_sip()
        if sip is None:
            sip = self.create_sip()

        if 'files' in sip.metadata:
            sip.metadata['fft'] = sip.metadata['files']
            del sip.metadata['files']

        sip.agents = [Agent(role='creator',
                            from_request_context=from_request_context)]
        self.update()
