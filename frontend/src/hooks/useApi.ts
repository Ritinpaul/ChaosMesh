import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { healthApi, envApi, demoApi } from '../api/client'
import type { InjectRequest } from '../types/api'

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: healthApi.getHealth,
  })
}

export function useEnvState() {
  return useQuery({
    queryKey: ['env', 'state'],
    queryFn: envApi.getState,
  })
}

export function useResetEpisode() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: (level: number) => envApi.reset(level),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['env', 'state'] })
      queryClient.invalidateQueries({ queryKey: ['health'] })
    },
  })
}

export function useInjectIncident() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: (data: InjectRequest) => demoApi.injectIncident(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['env', 'state'] })
    },
  })
}

export function useDemoScenarios() {
  return useQuery({
    queryKey: ['demo', 'scenarios'],
    queryFn: demoApi.getScenarios,
    staleTime: 30_000,
  })
}

export function useDemoPrecomputed() {
  return useQuery({
    queryKey: ['demo', 'precomputed'],
    queryFn: demoApi.getPrecomputed,
    staleTime: 60_000,
  })
}
