This repo is suitable for deploying tado_aa.py to Openshift/OKD (maybe Cloud)    
For details check https://sascha-brockel.de/tado-auto-assist-kostenlos/ 
    
For Google Cloud deployment check [GCR](./README_GoogleCloud.md)

# Install
```sh
oc new-project tado

# Keep the quotes as they escape any special characters in the password
oc create secret generic tado --from-literal=USERNAME='myemail@example.com' --from-literal=PASSWORD='mypass'

oc new-app https://github.com/hunter86bg/tado_aa -e USERNAME='myemail@example.com' -e PASSWORD='mypass' -o yaml >> tado_new_app.yaml

# Edit the newly generated file to add a refference to the secrets
vim tado_new_app.yaml

# Change the environment part. The result will look like this:
cat tado_new_app.yaml
<OUTPUT TRUNCATED>
      spec:
        containers:
        - env:
          - name: PASSWORD
            valueFrom:
              secretKeyRef:
                key: PASSWORD
                name: tado
          - name: USERNAME
            valueFrom:
              secretKeyRef:
                key: USERNAME
                name: tado
          image: ' '
          name: tadoaa
          ports:
          - containerPort: 8080
            protocol: TCP
          resources: {}
  status: {}
<OUTPUT TRUNCATED>

# Change the Liveliness , Readiness and Startup Probes. The spec should look like:    
<OUTPUT TRUNCATED>
spec:
      containers:
      - env:
        - name: PASSWORD
          valueFrom:
            secretKeyRef:
              key: PASSWORD
              name: tado
        - name: USERNAME
          valueFrom:
            secretKeyRef:
              key: USERNAME
              name: tado
        image: ' '
        imagePullPolicy: IfNotPresent
        livenessProbe:
          failureThreshold: 3
          httpGet:
            path: /
            port: 8080
            scheme: HTTP
          initialDelaySeconds: 5
          periodSeconds: 10
          successThreshold: 1
          timeoutSeconds: 2
        name: tadoaa
        ports:
        - containerPort: 8080
          protocol: TCP
        readinessProbe:
          failureThreshold: 3
          httpGet:
            path: /
            port: 8080
            scheme: HTTP
          initialDelaySeconds: 5
          periodSeconds: 10
          successThreshold: 1
          timeoutSeconds: 2
        resources: {}
        startupProbe:
          failureThreshold: 3
          httpGet:
            path: /
            port: 8080
            scheme: HTTP
          initialDelaySeconds: 5
          periodSeconds: 10
          successThreshold: 1
          timeoutSeconds: 2
<OUTPUT TRUNCATED>
# Apply the yaml    
oc apply -f tado_new_app.yaml

# Check the build status
oc logs -f buildconfig/tadoaa

# Once it's done , check the pod logs
oc logs -f $(oc get pods -o name | grep -v build)

# Go to the tado app and switch geo fencing to 'AWAY' if you are currently at home or to 'HOME' if there is nobody at home
# The status should change in less than a minute
```
