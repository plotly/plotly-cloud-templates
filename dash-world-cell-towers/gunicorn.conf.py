# Each worker process loads its own copy of the ~50M row dataset (several GB), so run a
# single worker and serve concurrent requests with threads that share that one copy
workers = 1
threads = 4
