Vercel page to show the latest USA Visa Bulletin.
It contains subscription service to send email notification upon new release of the Bulletin.
 - Subscription is managed with Neon database

Github Action workflow has been set to deploy new commit per 30 minutes to check the Visa Bulletin board and send emails to subscribers if there's new bulletin.
 - When the 'master' branch is pushed, the Vercel page will be automatically deployed.

The official Visa Bulletin page link is set to : https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin/%Y/visa-bulletin-for-%B-%Y.html
 - %Y : 2025
 - %B : January, February...

Vercel project page : https://vercel.com/karingzs-projects/visa-bulletin-checker

