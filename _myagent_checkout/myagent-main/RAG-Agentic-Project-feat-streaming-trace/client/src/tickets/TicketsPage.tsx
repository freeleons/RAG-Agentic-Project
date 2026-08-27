import { useEffect, useState } from "react";
import AddIcon from "@mui/icons-material/Add";
import ConfirmationNumberIcon from "@mui/icons-material/ConfirmationNumber";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import RefreshIcon from "@mui/icons-material/Refresh";
import SearchIcon from "@mui/icons-material/Search";
import TicketChatWidget from "./TicketChatWidget";


import {
  Alert,

  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Chip,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  Grid,
  IconButton,
  InputAdornment,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { api } from "../api";
import type { Conversation, Ticket, TicketFilters, UiMessage } from "../types";

interface Props {
  selectedConversationId?: number | null;
  onSelectConversation?: (id: number) => void;
  onOpenFullChat?: (id: number) => void;
  conversations?: Conversation[];
  onNewConversation?: () => void;
  onRefreshConversations?: () => void;
  globalBusy?: boolean;
  globalMessages?: UiMessage[];
  globalPendingAction?: { runId: number; tool: string; arguments: any } | null;
  onGlobalSend?: (goal: string) => void;
  onGlobalStop?: () => void;
  onGlobalConfirm?: (approved: boolean) => void;
  refreshVersion?: number;
}

const STATUS_COLOR: Record<string, { bg: string; color: string; label: string }> = {
  open: { bg: "#DCFCE7", color: "#166534", label: "Open" },
  in_progress: { bg: "#FEF3C7", color: "#92400E", label: "In Progress" },
  resolved: { bg: "#EEF2FF", color: "#3730A3", label: "Resolved" },
  closed: { bg: "#F1F5F9", color: "#475569", label: "Closed" },
};

const PRIORITY_COLOR: Record<string, { bg: string; color: string; label: string }> = {
  urgent: { bg: "#FFE4E6", color: "#9F1239", label: "Urgent" },
  high: { bg: "#FFEDD5", color: "#9A3412", label: "High" },
  medium: { bg: "#FEF9C3", color: "#854D0E", label: "Medium" },
  low: { bg: "#F0FDF4", color: "#166534", label: "Low" },
};

export default function TicketsPage({
  selectedConversationId,
  onSelectConversation,
  onOpenFullChat,
  conversations,
  onNewConversation,
  onRefreshConversations,
  globalBusy,
  globalMessages,
  globalPendingAction,
  onGlobalSend,
  onGlobalStop,
  onGlobalConfirm,
  refreshVersion,
}: Props) {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [widgetPrompt, setWidgetPrompt] = useState<string | undefined>(undefined);

  // Filters state
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");

  // Create Modal State
  const [openCreate, setOpenCreate] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newPriority, setNewPriority] = useState("medium");
  const [newCategory, setNewCategory] = useState("IT");

  // Edit Modal State
  const [editTicket, setEditTicket] = useState<Ticket | null>(null);
  const [editStatus, setEditStatus] = useState("");
  const [editPriority, setEditPriority] = useState("");

  // Delete Confirm Modal
  const [deleteId, setDeleteId] = useState<number | null>(null);

  const fetchTickets = () => {
    setLoading(true);
    setError(null);
    const filters: TicketFilters = {};
    if (statusFilter !== "all") filters.status = statusFilter;
    if (priorityFilter !== "all") filters.priority = priorityFilter;
    if (categoryFilter !== "all") filters.category = categoryFilter;
    if (search.trim()) filters.q = search.trim();

    api
      .getTickets(filters)
      .then(setTickets)
      .catch((err) => setError(err.message || "Failed to load tickets"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchTickets();
  }, [statusFilter, priorityFilter, categoryFilter, refreshVersion]);


  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchTickets();
  };

  const handleCreate = async () => {
    setError("Creating tickets is disabled.");
  };

  const handleUpdate = async () => {
    if (!editTicket) return;
    try {
      await api.updateTicket(editTicket.id, {
        status: editStatus,
        priority: editPriority,
      });
      setEditTicket(null);
      fetchTickets();
    } catch (err: any) {
      setError(err.message || "Failed to update ticket");
    }
  };

  const handleDelete = async () => {
    setError("Deleting tickets is disabled.");
  };

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      {/* Header Bar */}
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: "-0.02em" }}>
            Support Ticket Management
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Manage IT, HR, and Billing support tickets or ask the AI agent to manage them for you.
          </Typography>
        </Box>
        <Stack direction="row" spacing={1.5}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={fetchTickets}
            disabled={loading}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setOpenCreate(true)}
          >
            New Ticket
          </Button>
        </Stack>
      </Stack>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Filter Controls Bar */}
      <Card variant="outlined" sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} sm={4}>
            <form onSubmit={handleSearchSubmit}>
              <TextField
                fullWidth
                size="small"
                placeholder="Search ticket title or details…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon fontSize="small" color="action" />
                    </InputAdornment>
                  ),
                }}
              />
            </form>
          </Grid>
          <Grid item xs={6} sm={2.6}>
            <FormControl fullWidth size="small">
              <InputLabel>Status</InputLabel>
              <Select
                value={statusFilter}
                label="Status"
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <MenuItem value="all">All Statuses</MenuItem>
                <MenuItem value="open">Open</MenuItem>
                <MenuItem value="in_progress">In Progress</MenuItem>
                <MenuItem value="resolved">Resolved</MenuItem>
                <MenuItem value="closed">Closed</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={6} sm={2.6}>
            <FormControl fullWidth size="small">
              <InputLabel>Priority</InputLabel>
              <Select
                value={priorityFilter}
                label="Priority"
                onChange={(e) => setPriorityFilter(e.target.value)}
              >
                <MenuItem value="all">All Priorities</MenuItem>
                <MenuItem value="urgent">Urgent</MenuItem>
                <MenuItem value="high">High</MenuItem>
                <MenuItem value="medium">Medium</MenuItem>
                <MenuItem value="low">Low</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={2.8}>
            <FormControl fullWidth size="small">
              <InputLabel>Category</InputLabel>
              <Select
                value={categoryFilter}
                label="Category"
                onChange={(e) => setCategoryFilter(e.target.value)}
              >
                <MenuItem value="all">All Categories</MenuItem>
                <MenuItem value="IT">IT Support</MenuItem>
                <MenuItem value="HR">HR & Personnel</MenuItem>
                <MenuItem value="Billing">Billing & Payroll</MenuItem>
                <MenuItem value="Facilities">Facilities</MenuItem>
                <MenuItem value="General">General</MenuItem>
              </Select>
            </FormControl>
          </Grid>
        </Grid>
      </Card>

      {/* Ticket Grid Cards */}
      <Grid container spacing={2.5}>
        {tickets.map((t) => {
          const sBadge = STATUS_COLOR[t.status] ?? STATUS_COLOR.open;
          const pBadge = PRIORITY_COLOR[t.priority] ?? PRIORITY_COLOR.medium;
          return (
            <Grid item xs={12} md={6} lg={4} key={t.id}>
              <Card
                variant="outlined"
                sx={{
                  height: "100%",
                  display: "flex",
                  flexDirection: "column",
                  transition: "transform 0.15s ease-in-out, box-shadow 0.15s ease-in-out",
                  "&:hover": {
                    boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
                  },
                }}
              >
                <CardContent sx={{ flexGrow: 1, pb: 1 }}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <ConfirmationNumberIcon fontSize="small" color="action" />
                      <Typography variant="subtitle2" color="text.secondary" sx={{ fontWeight: 700 }}>
                        Ticket #{t.id}
                      </Typography>
                    </Stack>
                    <Chip
                      size="small"
                      label={t.category}
                      sx={{ height: 20, fontSize: "0.65rem", fontWeight: 700, bgcolor: "#F1F5F9" }}
                    />
                  </Stack>

                  <Typography variant="h6" sx={{ fontSize: "1rem", mb: 1, fontWeight: 700 }}>
                    {t.title}
                  </Typography>

                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{
                      mb: 2,
                      display: "-webkit-box",
                      WebkitLineClamp: 3,
                      WebkitBoxOrient: "vertical",
                      overflow: "hidden",
                    }}
                  >
                    {t.description}
                  </Typography>

                  <Stack direction="row" spacing={1} alignItems="center">
                    <Chip
                      size="small"
                      label={sBadge.label}
                      sx={{ bgcolor: sBadge.bg, color: sBadge.color, fontWeight: 700 }}
                    />
                    <Chip
                      size="small"
                      label={pBadge.label}
                      sx={{ bgcolor: pBadge.bg, color: pBadge.color, fontWeight: 700 }}
                    />
                  </Stack>
                </CardContent>

                <CardActions sx={{ justifyContent: "flex-end", px: 2, pb: 2, pt: 0 }}>
                  <Box>
                    <IconButton
                      size="small"
                      onClick={() => {
                        setEditTicket(t);
                        setEditStatus(t.status);
                        setEditPriority(t.priority);
                      }}
                    >
                      <EditOutlinedIcon fontSize="small" />
                    </IconButton>
                    <IconButton
                      size="small"
                      color="error"
                      onClick={() => setDeleteId(t.id)}
                    >
                      <DeleteOutlineIcon fontSize="small" />
                    </IconButton>
                  </Box>
                </CardActions>


              </Card>
            </Grid>
          );
        })}
        {tickets.length === 0 && !loading && (
          <Grid item xs={12}>
            <Card variant="outlined" sx={{ p: 4, textAlign: "center" }}>
              <Typography variant="h6" color="text.secondary" sx={{ mb: 1 }}>
                No support tickets found
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Create a new ticket using the button above, or ask the chatbot to file one for you!
              </Typography>
              <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpenCreate(true)}>
                New Ticket
              </Button>
            </Card>
          </Grid>
        )}
      </Grid>

      {/* Create Ticket Dialog */}
      <Dialog open={openCreate} onClose={() => setOpenCreate(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Create Support Ticket</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField
              fullWidth
              label="Ticket Title"
              placeholder="e.g., Laptop display flickering on USB-C dock"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              required
            />
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <FormControl fullWidth>
                  <InputLabel>Priority</InputLabel>
                  <Select
                    value={newPriority}
                    label="Priority"
                    onChange={(e) => setNewPriority(e.target.value)}
                  >
                    <MenuItem value="low">Low</MenuItem>
                    <MenuItem value="medium">Medium</MenuItem>
                    <MenuItem value="high">High</MenuItem>
                    <MenuItem value="urgent">Urgent</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={6}>
                <FormControl fullWidth>
                  <InputLabel>Category</InputLabel>
                  <Select
                    value={newCategory}
                    label="Category"
                    onChange={(e) => setNewCategory(e.target.value)}
                  >
                    <MenuItem value="IT">IT Support</MenuItem>
                    <MenuItem value="HR">HR & Personnel</MenuItem>
                    <MenuItem value="Billing">Billing & Payroll</MenuItem>
                    <MenuItem value="Facilities">Facilities</MenuItem>
                    <MenuItem value="General">General</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
            <TextField
              fullWidth
              multiline
              rows={4}
              label="Detailed Problem Description"
              placeholder="Describe the issue, error messages, or request in detail…"
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              required
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setOpenCreate(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleCreate}
            disabled={!newTitle.trim() || !newDesc.trim()}
          >
            Create Ticket
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit Ticket Dialog */}
      <Dialog open={!!editTicket} onClose={() => setEditTicket(null)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontWeight: 700 }}>Update Ticket #{editTicket?.id}</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
              {editTicket?.title}
            </Typography>
            <FormControl fullWidth>
              <InputLabel>Status</InputLabel>
              <Select
                value={editStatus}
                label="Status"
                onChange={(e) => setEditStatus(e.target.value)}
              >
                <MenuItem value="open">Open</MenuItem>
                <MenuItem value="in_progress">In Progress</MenuItem>
                <MenuItem value="resolved">Resolved</MenuItem>
                <MenuItem value="closed">Closed</MenuItem>
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel>Priority</InputLabel>
              <Select
                value={editPriority}
                label="Priority"
                onChange={(e) => setEditPriority(e.target.value)}
              >
                <MenuItem value="low">Low</MenuItem>
                <MenuItem value="medium">Medium</MenuItem>
                <MenuItem value="high">High</MenuItem>
                <MenuItem value="urgent">Urgent</MenuItem>
              </Select>
            </FormControl>
          </Stack>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setEditTicket(null)}>Cancel</Button>
          <Button variant="contained" onClick={handleUpdate}>
            Save Changes
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteId !== null} onClose={() => setDeleteId(null)}>
        <DialogTitle sx={{ fontWeight: 700 }}>Delete Ticket #{deleteId}?</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            Are you sure you want to delete this ticket? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setDeleteId(null)}>Cancel</Button>
          <Button color="error" variant="contained" onClick={handleDelete}>
            Delete Ticket
          </Button>
        </DialogActions>
      </Dialog>

      {/* Floating AI Triage Assistant Widget */}
      <TicketChatWidget
        initialPrompt={widgetPrompt}
        onClearInitialPrompt={() => setWidgetPrompt(undefined)}
        onTicketUpdated={fetchTickets}
        selectedConversationId={selectedConversationId}
        onSelectConversation={onSelectConversation}
        onOpenFullChat={onOpenFullChat}
        conversations={conversations}
        onNewConversation={onNewConversation}
        onRefreshConversations={onRefreshConversations}
        globalBusy={globalBusy}
        globalMessages={globalMessages}
        globalPendingAction={globalPendingAction}
        onGlobalSend={onGlobalSend}
        onGlobalStop={onGlobalStop}
        onGlobalConfirm={onGlobalConfirm}
      />


    </Container>
  );
}

