#!/usr/local/bin/bash
set -e

# inspire from https://github.com/dewe/mfauth/blob/master/mfauth.sh

#OTP_ID=$1
#OTP=$(op item get $OTP_ID --otp)
#DEVICE_ID=$(aws iam list-mfa-devices | jq -r '.MFADevices[0].SerialNumber')
#
#RESULT=$(aws sts get-session-token --serial-number $DEVICE_ID --duration-seconds 129600 --token-code $OTP)

SESSION=${AWS_PROFILE}
echo "Session: ${SESSION}"

declare -A ROLES
ROLES=(
  # AO
  ["ao-staging"]="arn:aws:iam::409141762494:role/Developer"
  ["bidap"]="arn:aws:iam::401357991636:role/data-scientist"
  ["bidap-admin"]="arn:aws:iam::401357991636:role/Administrator"
  # CORE
  ## Sandbox
  ["core-dw-sandbox"]="arn:aws:iam::763818062585:role/developer"
  ["core-dw-sandbox-admin"]="arn:aws:iam::763818062585:role/terraformer"
  ## Staging
  ["core-staging"]="arn:aws:iam::986102188572:role/developer"
  ["core-staging-admin"]="arn:aws:iam::986102188572:role/terraformer"
  ["core-sci-staging"]="arn:aws:iam::248201996333:role/developer"
  ["core-sci-staging-admin"]="arn:aws:iam::248201996333:role/terraformer"
  ["core-dw-staging"]="arn:aws:iam::761760642465:role/developer"
  ["core-dw-staging-admin"]="arn:aws:iam::761760642465:role/terraformer"
  ## Production
  ["core-production"]="arn:aws:iam::402295273060:role/developer"
  ["core-production-admin"]="arn:aws:iam::402295273060:role/terraformer"
  ["core-sci-production"]="arn:aws:iam::927353741421:role/developer"
  ["core-sci-production-admin"]="arn:aws:iam::927353741421:role/terraformer"
  ["core-dw-production"]="arn:aws:iam::387954691739:role/developer"
  ["core-dw-production-admin"]="arn:aws:iam::387954691739:role/terraformer"

  ["core-root-terraformer"]="arn:aws:iam::402295273060:role/terraformer"
  # UDP
  ["udp-ao-staging"]="arn:aws:iam::409141762494:role/adapters-developer"
)

declare -A ACCOUNTS
ACCOUNTS=(
  # AO
  ["ao-staging"]="loic.fontaine-ao"
  ["bidap"]="loic.fontaine-ao"
  ["bidap-admin"]="loic.fontaine-ao"
  # CORE
  ["core-dw-sandbox"]="loic.fontaine-core"
  ["core-dw-sandbox-admin"]="loic.fontaine-core"
  ["core-staging"]="loic.fontaine-core"
  ["core-staging-admin"]="loic.fontaine-core"
  ["core-sci-staging"]="loic.fontaine-core"
  ["core-sci-staging-admin"]="loic.fontaine-core"
  ["core-dw-staging"]="loic.fontaine-core"
  ["core-dw-staging-admin"]="loic.fontaine-core"
  ["core-production"]="loic.fontaine-core"
  ["core-production-admin"]="loic.fontaine-core"
  ["core-sci-production"]="loic.fontaine-core"
  ["core-sci-production-admin"]="loic.fontaine-core"
  ["core-dw-production"]="loic.fontaine-core"
  ["core-dw-production-admin"]="loic.fontaine-core"
  ["core-root-terraformer"]="loic.fontaine-core"
  # UDP
  ["udp-ao-staging"]="loic.fontaine"
)

ROLE=${ROLES[${SESSION}]}
ACCOUNT=${ACCOUNTS[${SESSION}]}

# fail if role or account is not defined
if [ -z ${ROLE} ]; then
  echo "Role not defined for ${SESSION}"
  exit 1
fi
if [ -z ${ACCOUNT} ]; then
  echo "Account not defined for ${SESSION}"
  exit 1
fi

#--duration-seconds 43200 \ An error occurred (ValidationError) when calling the AssumeRole operation: The requested DurationSeconds exceeds the 1 hour session limit for roles assumed by role chaining.

#while [ $(date +%H:%M) != "04:00" ]; do sleep 1; done

while true; do
  export $(printf "AWS_ACCESS_KEY_ID=%s AWS_SECRET_ACCESS_KEY=%s AWS_SESSION_TOKEN=%s" \
$(aws-vault exec ${ACCOUNT} -- aws sts assume-role \
--role-arn ${ROLE} \
--role-session-name MySessionName \
--query "Credentials.[AccessKeyId,SecretAccessKey,SessionToken]" \
--output text))

  aws configure set aws_access_key_id ${AWS_ACCESS_KEY_ID} --profile ${SESSION}
  aws configure set aws_secret_access_key ${AWS_SECRET_ACCESS_KEY} --profile ${SESSION}
  aws configure set aws_session_token ${AWS_SESSION_TOKEN} --profile ${SESSION}
  aws configure set region us-west-2 --profile ${SESSION}
  echo "Session: ${SESSION} refreshed"
  sleep 3400
done

#echo ${SESSION}

#https://signin.aws.amazon.com/oauth?Action=logout&redirect_uri=https://aws.amazon.com