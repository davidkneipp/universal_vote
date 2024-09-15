# Universal Vote

Software for anonymous, pre-authorized voting in a secure manner.

## What it does

Provides a server and instructions for pre-configured users to vote on a given matter.
Votes are kept anonymous and voting is kept cryptographically secure.
Ties are resolved by a delegated administrator.

## How it works

1. A vote with given options is setup using the provided webpage.
  - During the setup, the following items are defined:
    - The vote options
    - Authorized user SSH public keys
    - Delegated administrator public key to resolve tie, if a tie occurs.
2. Each user follows the instructions on the included script to encrypt a plaintext vote using their SSH key.
3. The encrypted vote file is then uploaded to the provided webpage.
4. The server then decrypts the vote, validates the text matches one of the given options and then marks the users public key as having voted.
4. The entire vote is completed when each user has cast their vote or the deadline is reached, whichever comes first.
5. If a tie is present, it is resolved by the delegated administrator.