## Prometheus

This playbook installs an Prometheus monitoring server


### Operation

1. Have an ubuntu 16.06 machine image
2. Set host for Prometheus server in `inventory`
3. Fill out the configuration in `config/prometheus-config.yml`
4. Run the playbook: `ansible-playbook prometheus.yml -u ubuntu -i inventory -v`




