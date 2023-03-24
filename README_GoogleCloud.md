I will summarize how to deploy tado_aa.py to Google cloud in this README
Keep in mind that this is not a step-by-step guide, but a short overview
of the process.
    
Google Cloud Run has a free tier and thanks to that the cost for the 
pilot run (2 months) was just $0.45, which is approximately $0.22 per
month.
    
# Prerequisites
- Google Cloud account
- One project where to deploy
- Budget to prevent unexpected costs (see https://cloud.google.com/blog/topics/developers-practitioners/protect-your-google-cloud-spending-budgets)
- 2 secrets tado_username (containing your tado e-mail) and tado_password
    
# Create Google cloud Build and Run
- Visit https://console.cloud.google.com
- From the left menu select "Cloud Run"
- Select "Create service"
- Pick "Continiously deploy new revisions from a source repository"
- Next, select "setup with cloud build"
- For "Source Repository" pick "GitHub" and then point to the git repo hunter86bg/tado_aa
- Select "Next"
- Select the branch (without the quotes): "^master$"
- For build type select "Dockerfile"
- For source location select (without the quotes): "/DockerFile/Dockerfile"
- Now Save the settings

## Configure the container parameters/autoscaling
- For "Minimum number of instances" set it to 1
- For "Maximum number of instances" set it again to 1
- Select "Internal" and "Require Authentication" in the next choices
- In the "Container,Network,Security" tab , set the memory to 128Mib (that's the minumum we can select)
- For CPU capacity select "<1" and in the field type 0.08 (that's the minumum Google allows us to select)
- Set "Maximum requests per container" to 1 (that's the minumum)
- In the secrets tab, select "Reference a secret" ->  tado_user
- For "Reference method" use "Exposed as environment variable" and for "Name 1" use  USERNAME and save
- "Reference a secret" -> tado_password , for "Reference method" use again "Exposed as environment variable"
and for "Name 1" use PASSWORD and save
- Click on the create button

    
    
Now the Cloud build will pull the docker file from the git repo , create a container and run it.
The 2 secrets are exposed as environment variables inside the container and the tado_aa.py can consume them.
