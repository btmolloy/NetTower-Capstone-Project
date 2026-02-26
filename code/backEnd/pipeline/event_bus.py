#Purpose: Thread-safe event queue/router. Sensors publish events; main consumes them.
#Inputs: Event objects published by sensors/active discovery.
#Outputs: Events returned to the consumer loop; supports publish(event) and get() semantics.