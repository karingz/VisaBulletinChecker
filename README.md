Vercel page to show the latest USA Visa Bulletin.
It contains subscription service to send email notification upon new release of the Bulletin.
 - Subscription is managed with Neon database

Github Action workflow has been set as serverless function to trigger check_bulletin() method every 5 minutes as to check the Visa Bulletin board and send emails to subscribers if there's new bulletin.
 - Also the page refresh by anyone will trigger check_bulletin() method.

The official Visa Bulletin page link is set to : https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin/%Y/visa-bulletin-for-%B-%Y.html
 - %Y : 2025
 - %B : January, February...

Vercel project page : https://vercel.com/karingzs-projects/visa-bulletin-checker

