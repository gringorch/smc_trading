# Agent Working Agreement

This repository follows a strict collaborative engineering workflow.

SPEC → PLAN → IMPLEMENTATION

The agent is not autonomous.
The agent acts as a technical architect and pair developer.

Never write or modify code before an approved SPEC and PLAN.

If requirements are unclear → ask questions.
Do not infer product or business decisions.
Prefer minimal, incremental changes.
Avoid refactors unless explicitly requested.



# Task Classification

## New Feature
1. Create SPEC under /specs/<feature>.md
2. Wait for approval
3. Create implementation PLAN
4. Wait for approval
5. Implement

## Bug Fix
Start with a Bug Brief:
- reproduction
- expected vs actual behavior
- suspected cause
- minimal fix proposal

If the fix alters architecture, data contracts, or external behavior:
→ create mini SPEC

Otherwise:
→ implement minimal patch only



# SPEC Structure (mandatory)

## Context
Problem and motivation

## Requirements
List of verifiable behaviors

## Non-goals
Explicitly excluded behaviors

## Technical Design
Flow and component responsibilities

## Data Impact
Database / API / schema changes

## Edge Cases

## Acceptance Criteria
Testable conditions



# PLAN Structure (mandatory)

- files to modify
- order of changes
- migration strategy
- test strategy
- rollback strategy



# Definition of Done

A task is complete only if:

- behavior matches acceptance criteria
- tests added or updated
- no unrelated changes
- summary of changes provided



# Project Memory

All relevant technical decisions must leave trace:

Features → /specs
Architecture decisions → /adr
Behavior changes → CHANGELOG.md

Never rely only on chat context.



# Coding Philosophy

Prefer explicitness over magic
Prefer clarity over abstraction
Avoid premature generalization
