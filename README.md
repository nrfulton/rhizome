# 10^4 maxima

> The tree imposes the verb 'to be,' but the fabric of the rhizome is the conjunction, 'and... and... and...'"

Rhizome is Mellea's multi-agent orchestration system. It is similar to
GasTown, in that it allows several different agents with pre-defined roles to
work together on constructing an artifact.

# rhizome

The `rhizome` class is a global singleton that tracks the current state of the
system. The currently running mellea programs, the location of the compost
pile, and the environment (which is typically either a document or a directory
-- think a single legal document, or a directory of Office documents, or a a
github repo. The rhizome also tracks state changes over time via a version
tracker; this is always git. If the artifact is a git repo then it uses the
`rhizome` branch on that repo. If the artiface is a raw directory without a
.git, then rhizome on startup creates a git repo and checks out the rhizome
branch.

The rhizome also offers some additional public
methods for commiting, adding, and deleting files. It also has a
`compost_pile` that contains both summaries of agent runs and off-chain
artifacts and abilable functions/agents.

There are several mellea contexts that offer views on the rhizome. These
RhizomeContexts differ in the level of granularity and focus that they
provide. The GlobalRhizomeView gives a very high level of the current state of
the rhizome. The RhizomeAgentAnthology gives a history of the major things
that agents have done in the rhizome.

The rhizome has a beat. On each beat, if a human has been invoked, all agents
are killed except the background agent and the next beat begins when the human
issues a command to the rhizome. This just results in the `humanity` list in
the rhizome getting an new string entry and this can and usually does
determine what happens next in the rhizome.

# Mellea Programs

Each "agent" is just a 3-tuple `needs, fun, abilities` that is basically a
hoare tuple:

 * `needs` is a list of preconditions that the agent needs. These should all
   be requirements.
 * `fun` is a mellea program with signature `r: rhizome, backend: Backend, ctx:
   Context, ...` where `...` are the Component and CBlock and sr
   arguments.
 * `abilities` is a list of things that the function will make true when it's
   done. These should all be requirements.

needs and abilities can be empty.

An agent gets started by the rhizome. And agent may also exit by adding a copy
of itself with changed needs, at which point it will be woken back up on the
next beat where the needs are satisfied.

There is a special agent called "Human" that the rhizome can use to request
help from a god-like figure, but this should be used sparingly because it
requires first killing all of the non-divergence-guarding agents.

# Inter-agent communication and multi-run state management

Rhizome also allows agents to communicate with each other and future instantiations of themselves via
context summaries dumped into the `compost_pile`. Each agent can add, update,
or remove from the compost pile.

The compost pile also contains previous runs of agents, which have the agent
implementation itself as well as a trace and summary..

# Background Agents

GasTown uses dogs to guard against certain types of divergence. Rhizome has a
similar concept, where a mellea program may be spawned as a background process
and can kill, start, or restart a particular agent. These programs run on
every beat.

One important background agent is the Gardener, which notices when a dormant
agnet's needs are satisfied and spawns that agent into the rhizome. The Gardener operates over a special Context
view on the rhizome.
