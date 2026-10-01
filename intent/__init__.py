"""Intent (catcher setup) module v0: IntentEstimate v1 records for broadcast decision frames.

The catcher's pre-pitch mitt position is a *proxy* for intent. Every record therefore carries
``is_intent_proxy=true`` and ``catcher_intent_verified=false``; accuracy fields stay ``null``
until they are measured (CHECKLIST / docs/INTENT_V0_WORK_ORDER.md, milestones M0-M3).
"""
