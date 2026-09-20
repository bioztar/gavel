• # Two-minute code defense

We treated Norma’s findings as useful engineering feedback, not as a checklist we had to follow blindly. For each finding, we asked: Is this a real risk in the
way Gavel is deployed? Can we fix it without hurting the live demo?

We fixed one issue in the calendar API. If starting a meeting failed, the /join endpoint sent the full error message back to the caller. That message could
include private details such as internal URLs, service names, or network information.

We changed this so the full error is only written to the server logs. The user now gets a simple 502 response: could not start the session. We also added a
test that creates a private upstream error and checks that none of its details appear in the response. This was a small change that improved security without
hiding anything useful from the user.

We chose to accept another finding: not every internal service API has its own authentication. This would be a serious problem if those services were open to
the internet, but that is not how our hackathon setup works.

Docker Compose exposes the Ears and Brain ports only on 127.0.0.1, and communication between services stays inside the Docker network. The Ears operator
console is private by default. If someone chooses to publish it through Traefik, the route only works when Basic Auth is configured.

Adding credentials to every internal request—and managing their rotation—would have made the connection between the voice, brain, and calendar services much
more complex during a time-limited build. We accepted this risk for our controlled setup and clearly documented the security boundary instead of ignoring the
finding.

Before using Gavel across multiple hosts or in production, we would add service identities, authentication between internal services, access rules for each
endpoint, and automatic credential rotation.
